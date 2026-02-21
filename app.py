import streamlit as st
import datetime
from extractor import extract_text_from_pdf, extract_invoice_fields
from auditor import audit_invoice

st.set_page_config(
    page_title="AI Invoice Auditor",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp { background-color: #f8fafc; color: #0f172a; font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1000px; }

    .hero { background: white; border-radius: 20px; border: 1px solid #e2e8f0; padding: 2.5rem 2rem; text-align: center; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .hero-badge { display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe; color: #2563eb; padding: 0.3rem 1rem; border-radius: 50px; font-size: 0.72rem; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 1rem; }
    .hero-title { font-size: 2.6rem; font-weight: 800; color: #0f172a; margin: 0 0 0.5rem 0; letter-spacing: -1px; }
    .hero-title span { color: #2563eb; }
    .hero-sub { color: #64748b; font-size: 1rem; }

    .steps-row { display: flex; gap: 0.75rem; margin-bottom: 2rem; flex-wrap: wrap; }
    .step-pill { background: white; border: 1px solid #e2e8f0; border-radius: 50px; padding: 0.5rem 1.2rem; font-size: 0.82rem; font-weight: 600; color: #475569; display: flex; align-items: center; gap: 0.5rem; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
    .step-pill .num { background: #eff6ff; color: #2563eb; width: 20px; height: 20px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 700; }

    .section-label { font-size: 0.7rem; font-weight: 700; color: #94a3b8; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1rem; margin-top: 0.5rem; }
    .upload-label { font-size: 0.75rem; font-weight: 700; color: #94a3b8; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 0.5rem; }

    .card { background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.2rem 1.4rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .metric-label { font-size: 0.7rem; font-weight: 600; color: #94a3b8; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 0.3rem; }
    .metric-value { font-size: 1.5rem; font-weight: 800; color: #0f172a; }
    .metric-value.blue  { color: #2563eb; }
    .metric-value.green { color: #059669; }
    .metric-value.red   { color: #dc2626; }

    .banner { border-radius: 16px; padding: 1.8rem 2rem; margin-bottom: 1.5rem; }
    .banner-correct    { background: #f0fdf4; border: 1.5px solid #86efac; }
    .banner-overcharge { background: #fff1f2; border: 1.5px solid #fca5a5; }
    .banner-icon  { font-size: 2.2rem; margin-bottom: 0.4rem; }
    .banner-title { font-size: 1.5rem; font-weight: 800; margin-bottom: 0.3rem; }
    .banner-correct    .banner-title { color: #15803d; }
    .banner-overcharge .banner-title { color: #b91c1c; }
    .banner-sub { font-size: 0.9rem; color: #64748b; }

    .reason-box       { background: #fff7ed; border-left: 4px solid #f97316; border-radius: 0 10px 10px 0; padding: 1rem 1.2rem; font-size: 0.88rem; color: #c2410c; font-family: 'JetBrains Mono', monospace; margin: 1rem 0; line-height: 1.8; }
    .reason-box-green { background: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 0 10px 10px 0; padding: 1rem 1.2rem; font-size: 0.88rem; color: #15803d; font-family: 'JetBrains Mono', monospace; margin: 1rem 0; line-height: 1.8; }

    .hsn-badge { display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; padding: 0.3rem 0.8rem; border-radius: 6px; font-size: 0.78rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-top: 0.5rem; }

    .cmp-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }
    .cmp-table th { background: #f8fafc; color: #64748b; padding: 0.75rem 1rem; text-align: left; font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #e2e8f0; }
    .cmp-table td { padding: 0.85rem 1rem; border-bottom: 1px solid #f1f5f9; color: #334155; font-family: 'JetBrains Mono', monospace; }
    .cmp-table tr:last-child td { border-bottom: none; }
    .cmp-table .ok  { color: #059669; font-weight: 600; }
    .cmp-table .bad { color: #dc2626; font-weight: 600; }
    .cmp-table .row-bad td { background: #fff8f8; }
    .cmp-table .row-ok  td { background: #fafffe; }

    .stDownloadButton > button { background: #2563eb !important; color: white !important; border: none !important; border-radius: 10px !important; padding: 0.65rem 1.8rem !important; font-weight: 700 !important; font-size: 0.9rem !important; width: 100% !important; font-family: 'Inter', sans-serif !important; box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important; }

    hr { border-color: #e2e8f0 !important; margin: 1.5rem 0 !important; }

    .footer { text-align: center; padding: 2rem 1rem 1rem; color: #cbd5e1; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; }
</style>
""", unsafe_allow_html=True)


# ── HERO ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-badge">⚡ AI Powered · Finance Audit Tool</div>
    <h1 class="hero-title">AI <span>Invoice</span> Auditor</h1>
    <p class="hero-sub">Upload any Indian vendor invoice → AI reads it → Detects GST overcharging using HSN codes & 2026 slab rates</p>
</div>
<div class="steps-row">
    <div class="step-pill"><span class="num">1</span> Upload Invoice PDF</div>
    <div class="step-pill"><span class="num">2</span> AI Extracts Fields</div>
    <div class="step-pill"><span class="num">3</span> HSN Code Detection</div>
    <div class="step-pill"><span class="num">4</span> GST Audit Result</div>
    <div class="step-pill"><span class="num">5</span> Download Report</div>
</div>
""", unsafe_allow_html=True)

# ── FILE UPLOAD ────────────────────────────────────────────────────────────────
st.markdown('<div class="upload-label">📤 Upload Vendor Invoice</div>', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Drop your invoice PDF here", type=["pdf"], label_visibility="collapsed")

def metric_card(col, label, value, color=""):
    col.markdown(f'<div class="card"><div class="metric-label">{label}</div><div class="metric-value {color}">{value}</div></div>', unsafe_allow_html=True)

if uploaded_file is not None:
    st.markdown("---")

    # STEP 1 — READ PDF
    st.markdown('<div class="section-label">📄 Step 1 — Reading PDF</div>', unsafe_allow_html=True)
    with st.spinner("Reading invoice PDF..."):
        pdf_text = extract_text_from_pdf(uploaded_file)

    if not pdf_text.strip():
        st.error("❌ Could not extract text. Please use a text-based PDF, not a scanned image.")
        st.stop()

    st.success(f"✅ Extracted {len(pdf_text)} characters from **{uploaded_file.name}**")
    with st.expander("🔍 View Raw Extracted Text"):
        st.code(pdf_text[:3000], language=None)

    st.markdown("---")

    # STEP 2 — AI EXTRACTION
    st.markdown('<div class="section-label">🤖 Step 2 — AI Field Extraction</div>', unsafe_allow_html=True)
    with st.spinner("AI is reading your invoice..."):
        try:
            fields = extract_invoice_fields(pdf_text)
        except Exception as e:
            st.error(f"❌ AI Extraction Failed: {str(e)}")
            st.markdown('<div class="reason-box">💡 <b>Check:</b> Open .env — should be exactly: GROQ_API_KEY=gsk_... (no spaces, no quotes)</div>', unsafe_allow_html=True)
            st.stop()

    st.success("✅ AI successfully extracted all invoice fields")
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">📊 Extracted Invoice Data</div>', unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    metric_card(c1, "🏢 Vendor",       str(fields.get("vendor_name", "N/A")))
    metric_card(c2, "💰 Billed Total",  f"₹{fields.get('invoice_total', 0):,}", "blue")
    metric_card(c3, "📊 GST %",         f"{fields.get('gst_percent', 0)}%")
    metric_card(c4, "📦 Rate/Unit",     f"₹{fields.get('rate_per_unit', 0)}")
    metric_card(c5, "🔢 Qty",           str(int(fields.get("quantity", 0))))

    st.markdown("---")

    # STEP 3 + 4 — HSN DETECTION + AUDIT
    st.markdown('<div class="section-label">🔖 Step 3 — HSN Code Detection & GST Audit</div>', unsafe_allow_html=True)
    with st.spinner("Detecting HSN code and auditing against 2026 GST rules..."):
        result = audit_invoice(fields, pdf_text)

    st.markdown("<br>", unsafe_allow_html=True)

    # HSN info card — always show
    st.markdown(f"""
    <div class="card" style="margin-bottom:1rem;">
        <div class="metric-label">🔖 Detected HSN Classification</div>
        <div style="margin-top:0.5rem;">
            <span class="hsn-badge">HSN {result.get("hsn_code", "N/A")}</span>
            <span style="margin-left:0.8rem;color:#475569;font-size:0.9rem;font-weight:600;">{result.get("hsn_description", "General Services")}</span>
        </div>
        <div style="margin-top:0.5rem;color:#64748b;font-size:0.82rem;">
            Applicable GST as per 2026 rules: <b>{result.get("expected_gst", 18)}%</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── CORRECT ───────────────────────────────────────────────────────────────
    if result["status"] == "correct":
        st.markdown("""
        <div class="banner banner-correct">
            <div class="banner-icon">✅</div>
            <div class="banner-title">Invoice Verified Correct</div>
            <div class="banner-sub">No discrepancies found. GST rate matches HSN classification and 2026 slab rules.</div>
        </div>
        """, unsafe_allow_html=True)
        st.balloons()

        col1, col2, col3 = st.columns(3)
        metric_card(col1, "Billed Total",   f"₹{result['billed_total']:,}",   "blue")
        metric_card(col2, "Expected Total", f"₹{result['expected_total']:,}", "green")
        metric_card(col3, "Overcharge",     "₹0",                             "green")

        st.markdown(f"""
        <div class="reason-box-green">
            ✅ <b>Audit Result:</b> {result["reason"]}<br><br>
            🔖 <b>HSN Code:</b> {result.get("hsn_code","N/A")} — {result.get("hsn_description","N/A")}<br>
            📋 <b>GST Slab (2026):</b> {result.get("expected_gst",18)}% applicable for this category
        </div>
        """, unsafe_allow_html=True)

    # ── OVERCHARGED ───────────────────────────────────────────────────────────
    elif result["status"] == "overcharged":
        st.markdown(f"""
        <div class="banner banner-overcharge">
            <div class="banner-icon">❌</div>
            <div class="banner-title">Overcharge Detected</div>
            <div class="banner-sub">Vendor: <b>{result["vendor"]}</b> · You were overcharged by <b>₹{result["overcharge"]:,}</b></div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        metric_card(col1, "💳 Billed Total",  f"₹{result['billed_total']:,}",   "red")
        metric_card(col2, "✅ Expected Total", f"₹{result['expected_total']:,}", "green")
        metric_card(col3, "⚠️ Overcharge",    f"₹{result['overcharge']:,}",     "red")

        st.markdown(f"""
        <div class="reason-box">
            ⚠️ <b>Reason:</b> {result["reason"]}<br><br>
            🔖 <b>HSN Code:</b> {result.get("hsn_code","N/A")} — {result.get("hsn_description","N/A")}<br>
            📋 <b>Correct GST Slab (2026):</b> {result.get("expected_gst",18)}% for this category | <b>Charged:</b> {result.get("billed_gst",0)}%
        </div>
        """, unsafe_allow_html=True)

        # Comparison Table
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">📋 Invoice vs Expected — Detailed Breakdown</div>', unsafe_allow_html=True)

        gst_ok  = result['billed_gst']  == result['expected_gst']
        rate_ok = result['billed_rate'] == result['expected_rate']

        def sc(ok): return '<span class="ok">✅ Match</span>' if ok else '<span class="bad">❌ Mismatch</span>'
        def rc(ok): return "row-ok" if ok else "row-bad"
        def vc(ok): return "ok" if ok else "bad"

        st.markdown(f"""
        <table class="cmp-table">
            <thead><tr><th>Field</th><th>Invoice Says</th><th>Expected (2026 GST Rules)</th><th>Status</th></tr></thead>
            <tbody>
                <tr class="row-ok"><td>Vendor Name</td><td>{result['vendor']}</td><td>{result['vendor']}</td><td>{sc(True)}</td></tr>
                <tr class="row-ok"><td>HSN Code</td><td colspan="2">{result.get("hsn_code","N/A")} — {result.get("hsn_description","N/A")}</td><td><span class="ok">✅ Detected</span></td></tr>
                <tr class="{rc(gst_ok)}"><td>GST %</td><td class="{vc(gst_ok)}">{result['billed_gst']}%</td><td class="ok">{result['expected_gst']}%</td><td>{sc(gst_ok)}</td></tr>
                <tr class="{rc(rate_ok)}"><td>Rate per Unit</td><td class="{vc(rate_ok)}">₹{result['billed_rate']}</td><td class="ok">₹{result['expected_rate']}</td><td>{sc(rate_ok)}</td></tr>
                <tr class="row-ok"><td>Quantity</td><td>{int(result['quantity'])}</td><td>{int(result['quantity'])}</td><td>{sc(True)}</td></tr>
                <tr class="{rc(rate_ok)}"><td>Base Amount</td><td class="{vc(rate_ok)}">₹{result['billed_rate'] * result['quantity']:,.2f}</td><td class="ok">₹{result['base_amount']:,.2f}</td><td>{sc(rate_ok)}</td></tr>
                <tr class="{rc(gst_ok)}"><td>GST Amount</td><td class="{vc(gst_ok)}">₹{result['gst_amount_billed']:,.2f}</td><td class="ok">₹{result['gst_amount_expected']:,.2f}</td><td>{sc(gst_ok)}</td></tr>
                <tr class="row-bad"><td><b>Final Total</b></td><td class="bad"><b>₹{result['billed_total']:,}</b></td><td class="ok"><b>₹{result['expected_total']:,}</b></td><td><span class="bad">❌ ₹{result['overcharge']:,} excess</span></td></tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)

    # ── STEP 5: DOWNLOAD ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-label">📥 Step 5 — Download Audit Report</div>', unsafe_allow_html=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if result["status"] == "overcharged":
        report = f"""
╔══════════════════════════════════════════════════════════╗
║              AI INVOICE AUDIT REPORT                     ║
╚══════════════════════════════════════════════════════════╝

Generated On   : {now}
Invoice File   : {uploaded_file.name}
Audit Status   : OVERCHARGE DETECTED

──────────────────────────────────────────────────────────
VENDOR & HSN CLASSIFICATION
──────────────────────────────────────────────────────────
Vendor Name    : {result['vendor']}
HSN Code       : {result.get("hsn_code","N/A")}
HSN Category   : {result.get("hsn_description","N/A")}
Quantity       : {int(result['quantity'])} units

──────────────────────────────────────────────────────────
FINANCIAL COMPARISON (2026 GST RULES)
──────────────────────────────────────────────────────────
                     INVOICE          EXPECTED
GST Applied    :     {result['billed_gst']}%               {result['expected_gst']}%
Rate per Unit  :     Rs{result['billed_rate']}             Rs{result['expected_rate']}
Base Amount    :     Rs{result['billed_rate'] * result['quantity']:,.2f}       Rs{result['base_amount']:,.2f}
GST Amount     :     Rs{result['gst_amount_billed']:,.2f}         Rs{result['gst_amount_expected']:,.2f}
Total Amount   :     Rs{result['billed_total']:,}         Rs{result['expected_total']:,}

──────────────────────────────────────────────────────────
AUDIT FINDING
──────────────────────────────────────────────────────────
Billed Total   : Rs{result['billed_total']:,}
Expected Total : Rs{result['expected_total']:,}
Overcharge     : Rs{result['overcharge']:,}
Reason         : {result['reason']}

──────────────────────────────────────────────────────────
APPLICABLE GST SLAB RATES (2026)
──────────────────────────────────────────────────────────
Valid GST Slabs : 0%, 3%, 5%, 12%, 18%, 40%
HSN {result.get("hsn_code","N/A")} ({result.get("hsn_description","N/A")})
attracts {result.get("expected_gst",18)}% GST as per 2026 rules.

RECOMMENDATION  : Raise a dispute with {result['vendor']} for
overcharging Rs{result['overcharge']:,} in violation of GST rules.

══════════════════════════════════════════════════════════
Generated by AI Invoice Auditor | Fellowship Builder Round
Powered by Groq AI + Streamlit + pdfplumber
HSN Code Reference: CBIC India 2026
══════════════════════════════════════════════════════════
"""
    elif result["status"] == "correct":
        report = f"""
╔══════════════════════════════════════════════════════════╗
║              AI INVOICE AUDIT REPORT                     ║
╚══════════════════════════════════════════════════════════╝

Generated On   : {now}
Invoice File   : {uploaded_file.name}
Audit Status   : INVOICE VERIFIED CORRECT

Vendor         : {result['vendor']}
HSN Code       : {result.get("hsn_code","N/A")}
HSN Category   : {result.get("hsn_description","N/A")}
Billed Total   : Rs{result['billed_total']:,}
Expected Total : Rs{result['expected_total']:,}
GST Applied    : {result['billed_gst']}% (Correct as per 2026 rules)
Overcharge     : Rs0

All values are correct as per 2026 Indian GST rules.
No action required.

══════════════════════════════════════════════════════════
Generated by AI Invoice Auditor | Fellowship Builder Round
Powered by Groq AI + Streamlit + pdfplumber
HSN Code Reference: CBIC India 2026
══════════════════════════════════════════════════════════
"""
    else:
        report = f"AI INVOICE AUDIT REPORT\nGenerated: {now}\nFile: {uploaded_file.name}\nStatus: UNKNOWN\n"

    st.download_button(
        label="⬇️  Download Full Audit Report (.txt)",
        data=report,
        file_name=f"audit_report_{uploaded_file.name.replace('.pdf','')}.txt",
        mime="text/plain"
    )

st.markdown('<div class="footer">AI INVOICE AUDITOR · FELLOWSHIP BUILDER ROUND · FINANCE PROBLEM TRACK<br>POWERED BY GROQ AI + STREAMLIT + PDFPLUMBER · HSN CODES AS PER CBIC INDIA 2026</div>', unsafe_allow_html=True)