import pandas as pd
import streamlit as st
import datetime
from extractor import extract_text_from_pdf, extract_invoice_fields
from auditor import audit_invoice
from risk_engine import (
    detect_exact_duplicate,
    detect_vendor_amount_duplicate,
    detect_suspicious_rounding,
    detect_rate_spike
)

# -----------------------------
# SESSION INIT
# -----------------------------
if "invoice_history" not in st.session_state:
    st.session_state.invoice_history = []

if "money_saved" not in st.session_state:
    st.session_state.money_saved = 0

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide"
)

st.title("AI Invoice Auditor")
st.caption("Upload invoice → Automatic Audit → Pay / Hold / Reject Decision")

# -----------------------------
# SIDEBAR — COMPANY CONFIG
# -----------------------------
st.sidebar.header("Company Configuration")

buyer_gstin = st.sidebar.text_input(
    "Enter Buyer GSTIN",
    value="27ABCDE1234F1Z5"
)

st.session_state.buyer_gstin = buyer_gstin

# -----------------------------
# SIDEBAR — MASTER UPLOADS
# -----------------------------
st.sidebar.header("Master Data Upload")

vendor_file = st.sidebar.file_uploader(
    "Upload Vendor Master CSV",
    type=["csv"],
    key="vendor_master"
)

contract_file = st.sidebar.file_uploader(
    "Upload Contract Master CSV",
    type=["csv"],
    key="contract_master"
)

if vendor_file:
    df_vendor = pd.read_csv(vendor_file)
    required_vendor_cols = {"vendor_name", "gstin", "state", "payment_terms"}
    if not required_vendor_cols.issubset(set(df_vendor.columns)):
        st.sidebar.error("Invalid Vendor Master format.")
    else:
        st.session_state.vendor_master = df_vendor
        st.sidebar.success("Vendor Master Loaded")

if contract_file:
    df_contract = pd.read_csv(contract_file)
    required_contract_cols = {
        "vendor_name",
        "item_description",
        "agreed_rate",
        "allowed_charges",
        "gst_allowed",
        "tolerance_percent"
    }
    if not required_contract_cols.issubset(set(df_contract.columns)):
        st.sidebar.error("Invalid Contract Master format.")
    else:
        st.session_state.contract_master = df_contract
        st.sidebar.success("Contract Master Loaded")

# -----------------------------
# DASHBOARD
# -----------------------------
history = st.session_state.invoice_history

total_invoices = len(history)
total_billed = sum(inv["amount"] for inv in history)
total_saved = st.session_state.money_saved
fail_count = sum(1 for inv in history if inv["status"] == "FAIL")
warning_count = sum(1 for inv in history if inv["status"] == "WARNING")

col1, col2, col3 = st.columns(3)
col1.metric("Invoices Audited", total_invoices)
col2.metric("Total Billed", f"₹{total_billed:,.2f}")
col3.metric("Money Saved", f"₹{total_saved:,.2f}")

col4, col5 = st.columns(2)
col4.metric("FAIL Count", fail_count)
col5.metric("WARNING Count", warning_count)

st.divider()

# -----------------------------
# FILE UPLOAD
# -----------------------------
uploaded_file = st.file_uploader("Upload Invoice (PDF)", type=["pdf"])

if uploaded_file:

    # STEP 1 — READ PDF
    with st.spinner("Reading PDF..."):
        pdf_text = extract_text_from_pdf(uploaded_file)

    if not pdf_text.strip():
        st.error("Could not extract text. Use text-based PDF.")
        st.stop()

    st.success("PDF text extracted successfully.")

    # STEP 2 — AI EXTRACTION
    with st.spinner("Extracting invoice data using AI..."):
        fields = extract_invoice_fields(pdf_text)

    st.success("Invoice fields extracted.")

    # -----------------------------
    # DISPLAY EXTRACTED DATA
    # -----------------------------
    st.subheader("Extracted Data")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Invoice Number", fields.get("invoice_number", "N/A"))
    col2.metric("Vendor", fields.get("vendor_name", "N/A"))
    col3.metric("Vendor State", fields.get("vendor_state", "N/A"))
    col4.metric("Invoice Date", fields.get("invoice_date", "N/A"))
    col5.metric("GST %", f"{fields.get('gst_percent', 0)}%")

    col6, col7, col8 = st.columns(3)
    col6.metric("CGST Amount", f"₹{fields.get('cgst_amount', 0):,.2f}")
    col7.metric("SGST Amount", f"₹{fields.get('sgst_amount', 0):,.2f}")
    col8.metric("IGST Amount", f"₹{fields.get('igst_amount', 0):,.2f}")

    col9, col10 = st.columns(2)
    col9.metric("Invoice Total", f"₹{fields.get('invoice_total', 0):,.2f}")
    col10.metric("Taxable Amount", f"₹{fields.get('taxable_amount', 0):,.2f}")

    st.divider()

    # STEP 3 — CORE AUDIT
    result = audit_invoice(fields, st.session_state.buyer_gstin)

    invoice_number = fields.get("invoice_number", "")
    vendor = result.get("vendor", "")
    amount = result.get("billed_total", 0)

    # -----------------------------
    # PHASE 1 INTELLIGENCE
    # -----------------------------
    if invoice_number and detect_exact_duplicate(invoice_number, history):
        result["issues"].append({
            "type": "CRITICAL",
            "message": "Exact duplicate invoice detected.",
            "impact": 0
        })
        result["status"] = "FAIL"
        result["recommendation"] = "REJECT"

    elif detect_vendor_amount_duplicate(vendor, amount, history):
        result["issues"].append({
            "type": "WARNING",
            "message": "Repeated identical billing detected.",
            "impact": 0
        })
        if result["status"] == "PASS":
            result["status"] = "WARNING"
            result["recommendation"] = "REVIEW"

    if detect_suspicious_rounding(amount):
        result["issues"].append({
            "type": "WARNING",
            "message": "Suspicious rounding pattern detected.",
            "impact": 0
        })

    spike_detected, spike_percent = detect_rate_spike(vendor, amount, history)
    if spike_detected:
        result["issues"].append({
            "type": "WARNING",
            "message": f"Invoice amount {spike_percent}% higher than vendor average.",
            "impact": 0
        })

    # -----------------------------
    # MONEY SAVED
    # -----------------------------
    total_impact = sum(issue.get("impact", 0) for issue in result["issues"])
    st.session_state.money_saved += total_impact

    # STORE HISTORY
    st.session_state.invoice_history.append({
        "invoice_number": invoice_number,
        "vendor": vendor,
        "amount": amount,
        "status": result["status"]
    })

    # -----------------------------
    # DISPLAY BUYER & VENDOR STATE
    # -----------------------------
    st.write("Buyer State (Derived from GSTIN):", result.get("buyer_state", "Unknown"))
    st.write("Vendor State:", result.get("vendor_state", "Unknown"))

    st.divider()

    # -----------------------------
    # DISPLAY RESULT
    # -----------------------------
    st.subheader("Audit Result")

    if result["status"] == "PASS":
        st.success("PASS ✅ — Invoice Cleared")
    elif result["status"] == "WARNING":
        st.warning("WARNING ⚠️ — Review Recommended")
    else:
        st.error("FAIL ❌ — Financial Risk Detected")

    st.write(f"Recommendation: {result['recommendation']}")

    st.divider()

    # Financial Impact
    if total_impact > 0:
        st.error(f"Potential Financial Leakage Detected: ₹{total_impact:,.2f}")

    # Risk Score
    risk_score = 0
    for issue in result["issues"]:
        if issue["type"] == "CRITICAL":
            risk_score += 30
        elif issue["type"] == "WARNING":
            risk_score += 10

    risk_score = min(risk_score, 100)

    st.subheader("Invoice Risk Score")
    st.progress(risk_score / 100)
    st.write(f"Risk Score: {risk_score}/100")

    st.divider()

    # Findings
    st.subheader("Audit Findings")
    for issue in result["issues"]:
        if issue["type"] == "CRITICAL":
            st.error(issue["message"])
        elif issue["type"] == "WARNING":
            st.warning(issue["message"])
        else:
            st.info(issue["message"])