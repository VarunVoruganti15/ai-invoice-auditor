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

def metric(label, value):
    st.metric(label, value)

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
    col3.metric("Invoice Date", fields.get("invoice_date", "N/A"))
    col4.metric("GST %", f"{fields.get('gst_percent', 0)}%")
    col5.metric("Invoice Total", f"₹{fields.get('invoice_total', 0):,.2f}")

    col6, col7 = st.columns(2)
    col6.metric("Rate per Unit", f"₹{fields.get('rate_per_unit', 0):,.2f}")
    col7.metric("Quantity", fields.get("quantity", 0))

    st.divider()

    # STEP 3 — CORE AUDIT
    with st.spinner("Running audit engine..."):
        result = audit_invoice(fields, pdf_text)

    # -----------------------------
    # INTELLIGENCE LAYER (PHASE 1)
    # -----------------------------
    invoice_number = fields.get("invoice_number", "")
    vendor = result.get("vendor", "")
    amount = result.get("billed_total", 0)

    # Duplicate — Exact
    if invoice_number and detect_exact_duplicate(invoice_number, history):
        result["issues"].append({
            "type": "CRITICAL",
            "message": "Exact duplicate invoice detected.",
            "impact": 0
        })
        result["status"] = "FAIL"
        result["recommendation"] = "REJECT"

    # Duplicate — Vendor + Amount
    elif detect_vendor_amount_duplicate(vendor, amount, history):
        result["issues"].append({
            "type": "WARNING",
            "message": "Repeated identical billing detected for vendor.",
            "impact": 0
        })
        if result["status"] == "PASS":
            result["status"] = "WARNING"
            result["recommendation"] = "REVIEW"

    # Suspicious Rounding
    if detect_suspicious_rounding(amount):
        result["issues"].append({
            "type": "WARNING",
            "message": "Suspicious rounding pattern detected.",
            "impact": 0
        })
        if result["status"] == "PASS":
            result["status"] = "WARNING"
            result["recommendation"] = "REVIEW"

    # Rate Spike
    spike_detected, spike_percent = detect_rate_spike(vendor, amount, history)
    if spike_detected:
        result["issues"].append({
            "type": "WARNING",
            "message": f"Invoice amount is {spike_percent}% higher than vendor average.",
            "impact": 0
        })
        if result["status"] == "PASS":
            result["status"] = "WARNING"
            result["recommendation"] = "REVIEW"

    # Track Money Saved
    st.session_state.money_saved += result.get("overcharge", 0)

    # Store Invoice in Session
    st.session_state.invoice_history.append({
        "invoice_number": invoice_number,
        "vendor": vendor,
        "amount": amount,
        "status": result["status"]
    })

    # -----------------------------
    # DISPLAY RESULTS
    # -----------------------------
    st.subheader("Audit Result")

    st.write("**Slab Regime Applied:**", result.get("slab_regime", "N/A"))
    st.write("**Classification Source:**", result.get("classification_source", "N/A"))
    st.write("**HSN/SAC Code:**", result.get("hsn_code", "N/A"))
    st.write("**Description:**", result.get("hsn_description", "N/A"))

    st.divider()

    status = result["status"]
    recommendation = result.get("recommendation", "")

    if status == "PASS":
        st.success("PASS ✅ — Invoice Cleared")
    elif status == "WARNING":
        st.warning("WARNING ⚠️ — Review Recommended")
    elif status == "FAIL":
        st.error("FAIL ❌ — Financial Risk Detected")

    st.write(f"**Recommendation:** {recommendation}")

    st.divider()

    col1, col2, col3 = st.columns(3)
    col1.metric("Billed Total", f"₹{result['billed_total']:,.2f}")
    col2.metric("Calculated Total", f"₹{result['expected_total']:,.2f}")
    col3.metric("Overcharge", f"₹{result['overcharge']:,.2f}")

    st.divider()

    st.subheader("Audit Findings")

    for issue in result["issues"]:
        if issue["type"] == "CRITICAL":
            st.error(f"CRITICAL: {issue['message']}")
        elif issue["type"] == "WARNING":
            st.warning(f"WARNING: {issue['message']}")
        else:
            st.info(f"INFO: {issue['message']}")

    st.divider()

    st.subheader("Calculation Breakdown")
    st.write("Base Amount:", f"₹{result['base_amount']:,.2f}")
    st.write("GST (Billed):", f"{result['billed_gst']}%")
    st.write("GST Amount (Billed):", f"₹{result['gst_amount_billed']:,.2f}")
    st.write("GST Amount (Expected):", f"₹{result['gst_amount_expected']:,.2f}")

    st.divider()

    # -----------------------------
    # DOWNLOAD REPORT
    # -----------------------------
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    findings_text = "\n".join(
        [f"{issue['type']}: {issue['message']}" for issue in result["issues"]]
    )

    report = f"""
AI INVOICE AUDIT REPORT
Generated On: {now}
File: {uploaded_file.name}

Vendor: {result['vendor']}
Invoice Date: {result.get('invoice_date','')}
Slab Regime: {result.get('slab_regime','')}
Classification Source: {result.get('classification_source','')}

HSN/SAC Code: {result.get('hsn_code','N/A')}
Description: {result.get('hsn_description','N/A')}

Status: {status}
Recommendation: {recommendation}

Billed Total: ₹{result['billed_total']:,.2f}
Calculated Total: ₹{result['expected_total']:,.2f}
Overcharge: ₹{result['overcharge']:,.2f}

Audit Findings:
{findings_text}
"""

    st.download_button(
        label="Download Audit Report",
        data=report,
        file_name=f"audit_report_{uploaded_file.name.replace('.pdf','')}.txt",
        mime="text/plain"
    )