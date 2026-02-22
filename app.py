import streamlit as st
import datetime
from extractor import extract_text_from_pdf, extract_invoice_fields
from auditor import audit_invoice

st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide"
)

st.title("AI Invoice Auditor")
st.caption("Upload an invoice → Extract → Validate GST → Detect Overcharge")

uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

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
    with st.spinner("Extracting invoice fields using AI..."):
        try:
            fields = extract_invoice_fields(pdf_text)
        except Exception as e:
            st.error(f"Extraction failed: {str(e)}")
            st.stop()

    st.success("Invoice fields extracted.")

    st.subheader("Extracted Data")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric("Vendor", fields.get("vendor_name", "N/A"))
    with col2:
        metric("Invoice Date", fields.get("invoice_date", "N/A"))
    with col3:
        metric("GST %", f"{fields.get('gst_percent', 0)}%")
    with col4:
        metric("Invoice Total", f"₹{fields.get('invoice_total', 0):,.2f}")

    col5, col6 = st.columns(2)
    with col5:
        metric("Rate per Unit", f"₹{fields.get('rate_per_unit', 0):,.2f}")
    with col6:
        metric("Quantity", fields.get("quantity", 0))

    st.divider()

    # STEP 3 — AUDIT
    with st.spinner("Auditing invoice..."):
        result = audit_invoice(fields, pdf_text)

    st.subheader("Audit Result")

    st.write("**Slab Regime Applied:**", result.get("slab_regime", "N/A"))
    st.write("**Classification Source:**", result.get("classification_source", "N/A"))
    st.write("**HSN/SAC Code:**", result.get("hsn_code", "N/A"))
    st.write("**Description:**", result.get("hsn_description", "N/A"))

    st.divider()

    if result["status"] == "correct":
        st.success("Invoice Verified Correct ✅")

        col1, col2, col3 = st.columns(3)
        with col1:
            metric("Billed Total", f"₹{result['billed_total']:,.2f}")
        with col2:
            metric("Expected Total", f"₹{result['expected_total']:,.2f}")
        with col3:
            metric("Overcharge", "₹0.00")

        st.info(result["reason"])

    elif result["status"] == "overcharged":
        st.error("Overcharge Detected ❌")

        col1, col2, col3 = st.columns(3)
        with col1:
            metric("Billed Total", f"₹{result['billed_total']:,.2f}")
        with col2:
            metric("Expected Total", f"₹{result['expected_total']:,.2f}")
        with col3:
            metric("Overcharge", f"₹{result['overcharge']:,.2f}")

        st.warning(result["reason"])

        st.divider()
        st.subheader("Detailed Breakdown")

        st.write("Base Amount:", f"₹{result['base_amount']:,.2f}")
        st.write("GST (Billed):", f"{result['billed_gst']}%")
        st.write("GST Amount (Billed):", f"₹{result['gst_amount_billed']:,.2f}")
        st.write("GST Amount (Expected):", f"₹{result['gst_amount_expected']:,.2f}")

    st.divider()

    # DOWNLOAD REPORT
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

Billed Total: ₹{result['billed_total']:,.2f}
Expected Total: ₹{result['expected_total']:,.2f}
Overcharge: ₹{result['overcharge']:,.2f}

Reason:
{result['reason']}
"""

    st.download_button(
        label="Download Audit Report",
        data=report,
        file_name=f"audit_report_{uploaded_file.name.replace('.pdf','')}.txt",
        mime="text/plain"
    )