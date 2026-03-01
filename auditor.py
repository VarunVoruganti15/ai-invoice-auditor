import datetime
import json
import os


# -----------------------------
# SAFE FLOAT
# -----------------------------
def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# -----------------------------
# GST SLAB LOGIC
# -----------------------------
def get_valid_slabs(invoice_date):
    old_slabs = [0, 3, 5, 12, 18, 40]
    new_slabs = [0, 5, 28, 40]

    try:
        date_obj = datetime.datetime.strptime(invoice_date, "%d-%m-%Y")
        cutoff = datetime.datetime(2025, 9, 22)

        if date_obj < cutoff:
            return old_slabs, "OLD"
        else:
            return new_slabs, "NEW"
    except:
        return old_slabs, "OLD"


# -----------------------------
# HSN / SAC LOOKUP
# -----------------------------
def lookup_code(code):
    try:
        master_path = os.path.join(os.path.dirname(__file__), "gst_rate_master.json")
        with open(master_path, "r") as f:
            master = json.load(f)

        gst_rate = master.get(code)

        if gst_rate is not None:
            return "GST Master Rate Applied", gst_rate

    except:
        pass

    return None, None


# -----------------------------
# MAIN AUDIT ENGINE
# -----------------------------
def audit_invoice(extracted_fields, pdf_text=""):

    vendor = extracted_fields.get("vendor_name", "").strip()
    invoice_date = extracted_fields.get("invoice_date", "")

    billed_total = safe_float(extracted_fields.get("invoice_total"))
    billed_gst = safe_float(extracted_fields.get("gst_percent"))
    billed_rate = safe_float(extracted_fields.get("rate_per_unit"))
    quantity = safe_float(extracted_fields.get("quantity"))

    declared_hsn = extracted_fields.get("hsn_code", "").strip()
    declared_sac = extracted_fields.get("sac_code", "").strip()

    valid_slabs, slab_type = get_valid_slabs(invoice_date)

    taxable_amount = safe_float(extracted_fields.get("taxable_amount"))
    gst_amount_declared = safe_float(extracted_fields.get("gst_amount"))

# If taxable amount available, trust it
    if taxable_amount > 0:
       base_amount = round(taxable_amount, 2)
    else:
         base_amount = round(billed_rate * quantity, 2)

    if gst_amount_declared > 0:
        gst_amount_billed = round(gst_amount_declared, 2)
    else:
        gst_amount_billed = round(base_amount * billed_gst / 100, 2)

    calculated_total = round(base_amount + gst_amount_billed, 2)

    

    issues = []
    classification_source = "Arithmetic Validation Only"
    expected_gst = billed_gst
    hsn_description = "Not Provided"

    code_used = declared_hsn or declared_sac

    # HSN / SAC validation
    if code_used:
        desc, gst_rate = lookup_code(code_used)

        if desc:
            hsn_description = desc
            classification_source = f"Declared Code ({code_used})"
        else:
            issues.append({
                "type": "INFO",
                "message": f"Code {code_used} not found in master. Basic GST validation applied.",
                "impact": 0
            })

        if gst_rate is not None:
            expected_gst = gst_rate

    # GST slab validation
    if billed_gst not in valid_slabs:
        issues.append({
            "type": "CRITICAL",
            "message": f"GST {billed_gst}% not valid under {slab_type} regime.",
            "impact": 0
        })

    if code_used and expected_gst != billed_gst:
        issues.append({
            "type": "CRITICAL",
            "message": f"GST applied {billed_gst}% but expected {expected_gst}%.",
            "impact": 0
        })

    # Math validation
    if abs(calculated_total - billed_total) > 1:
        impact = round(billed_total - calculated_total, 2)
        issues.append({
            "type": "CRITICAL",
            "message": f"Invoice total mismatch. Expected ₹{calculated_total}, billed ₹{billed_total}.",
            "impact": max(impact, 0)
        })

    overcharge = max(round(billed_total - calculated_total, 2), 0)

    # Decision engine
    critical_exists = any(i["type"] == "CRITICAL" for i in issues)
    warning_exists = any(i["type"] == "WARNING" for i in issues)

    if critical_exists and overcharge > 1:
        status = "FAIL"
        recommendation = "REJECT"
    elif critical_exists:
        status = "FAIL"
        recommendation = "HOLD"
    elif warning_exists:
        status = "WARNING"
        recommendation = "REVIEW"
    else:
        status = "PASS"
        recommendation = "PAY"

    if not issues:
        issues.append({
            "type": "INFO",
            "message": "Invoice passed all validation checks.",
            "impact": 0
        })

    return {
        "status": status,
        "recommendation": recommendation,
        "vendor": vendor,
        "invoice_date": invoice_date,
        "slab_regime": slab_type,
        "classification_source": classification_source,
        "hsn_code": code_used or "N/A",
        "hsn_description": hsn_description,
        "billed_total": billed_total,
        "expected_total": calculated_total,
        "overcharge": overcharge,
        "billed_gst": billed_gst,
        "expected_gst": expected_gst,
        "billed_rate": billed_rate,
        "quantity": quantity,
        "issues": issues,
        "base_amount": base_amount,
        "gst_amount_expected": round(base_amount * expected_gst / 100, 2),
        "gst_amount_billed": gst_amount_billed
    }