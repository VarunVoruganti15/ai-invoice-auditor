import json
import os
from datetime import datetime


# ---------- LOAD MASTER DATA ----------

def load_contract():
    contract_path = os.path.join(os.path.dirname(__file__), "contract.json")
    with open(contract_path, "r") as f:
        return json.load(f)


# ---------- SAFE NUMBER PARSER ----------

def safe_float(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except:
        return 0.0


# ---------- GST SLAB SELECTION ----------

def get_valid_slabs(invoice_date_str):
    """
    If date < 22-09-2025 → Old Slabs
    If date >= 22-09-2025 → New Slabs
    """

    OLD_SLABS = [0, 5, 12, 18, 28]
    NEW_SLABS = [0, 5, 28, 40]

    try:
        invoice_date = datetime.strptime(invoice_date_str, "%d-%m-%Y")
        cutoff = datetime.strptime("22-09-2025", "%d-%m-%Y")

        if invoice_date < cutoff:
            return OLD_SLABS, "OLD"
        else:
            return NEW_SLABS, "NEW"

    except:
        # If date missing or invalid → assume old slabs (safer fallback)
        return OLD_SLABS, "OLD"


# ---------- LOOKUP DECLARED HSN/SAC ----------

def lookup_code(code):
    contract = load_contract()
    master = contract.get("hsn_master", {})
    return master.get(code)


# ---------- MAIN AUDIT FUNCTION ----------

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

    base_amount = round(billed_rate * quantity, 2)
    gst_amount_billed = round(base_amount * billed_gst / 100, 2)
    calculated_total = round(base_amount + gst_amount_billed, 2)

    reasons = []
    classification_source = "Arithmetic Validation Only"
    expected_gst = billed_gst
    hsn_description = "Not Provided"

    # ---------- PRIORITY 1: DECLARED HSN ----------
    if declared_hsn:
        code_data = lookup_code(declared_hsn)
        if code_data:
            expected_gst = code_data["gst_percent"]
            hsn_description = code_data["description"]
            classification_source = f"Declared HSN ({declared_hsn})"

        else:
            reasons.append(f"Declared HSN {declared_hsn} not found in master data")

    # ---------- PRIORITY 2: DECLARED SAC ----------
    elif declared_sac:
        code_data = lookup_code(declared_sac)
        if code_data:
            expected_gst = code_data["gst_percent"]
            hsn_description = code_data["description"]
            classification_source = f"Declared SAC ({declared_sac})"

        else:
            reasons.append(f"Declared SAC {declared_sac} not found in master data")

    # ---------- GST SLAB VALIDATION ----------
    if billed_gst not in valid_slabs:
        reasons.append(
            f"GST {billed_gst}% is not valid under {slab_type} slab regime "
            f"(Valid slabs: {valid_slabs})"
        )

    # ---------- GST MISMATCH ----------
    if declared_hsn or declared_sac:
        if billed_gst != expected_gst:
            reasons.append(
                f"GST applied {billed_gst}% but code requires {expected_gst}%"
            )

    # ---------- ARITHMETIC VALIDATION ----------
    if abs(calculated_total - billed_total) > 1:
        reasons.append(
            f"Invoice total mismatch. Expected ₹{calculated_total}, "
            f"but billed ₹{billed_total}"
        )

    overcharge = max(round(billed_total - calculated_total, 2), 0)

    # ---------- FINAL RESULT ----------
    if not reasons:
        status = "correct"
        reason_text = "Invoice is mathematically correct and GST slab valid."
    else:
        status = "overcharged"
        reason_text = " | ".join(reasons)

    return {
        "status": status,
        "vendor": vendor,
        "invoice_date": invoice_date,
        "slab_regime": slab_type,
        "classification_source": classification_source,
        "hsn_code": declared_hsn or declared_sac or "N/A",
        "hsn_description": hsn_description,
        "billed_total": billed_total,
        "expected_total": calculated_total,
        "overcharge": overcharge,
        "billed_gst": billed_gst,
        "expected_gst": expected_gst,
        "billed_rate": billed_rate,
        "expected_rate": billed_rate,
        "quantity": quantity,
        "reason": reason_text,
        "base_amount": base_amount,
        "gst_amount_expected": gst_amount_billed,
        "gst_amount_billed": gst_amount_billed
    }