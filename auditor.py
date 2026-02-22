import os
import json
import pandas as pd
from datetime import datetime


# ---------- SAFE FLOAT ----------

def safe_float(value):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except:
        return 0.0


# ---------- LOAD EXCEL CODE MASTER ----------

def load_excel_codes():
    base_path = os.path.dirname(__file__)
    path = os.path.join(base_path, "gst_master.xlsx")

    codes = {}

    if not os.path.exists(path):
        return codes

    # Load HSN sheet
    hsn_df = pd.read_excel(path, sheet_name="HSN_MSTR")
    for _, row in hsn_df.iterrows():
        code = str(row["HSN_CD"]).strip()
        description = str(row["HSN_Description"]).strip()
        codes[code] = description

    # Load SAC sheet
    sac_df = pd.read_excel(path, sheet_name="SAC_MSTR")
    for _, row in sac_df.iterrows():
        code = str(row["SAC_CD"]).strip()
        description = str(row["SAC_Description"]).strip()
        codes[code] = description

    return codes


# ---------- LOAD GST RATE MASTER ----------

def load_gst_rates():
    base_path = os.path.dirname(__file__)
    path = os.path.join(base_path, "gst_rate_master.json")

    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)

    return {}


EXCEL_CODES = load_excel_codes()
GST_RATES = load_gst_rates()


# ---------- GST SLABS ----------

def get_valid_slabs(invoice_date_str):
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
        return OLD_SLABS, "OLD"


# ---------- LOOKUP ----------

def lookup_code(code):
    if not code:
        return None, None

    code = str(code).strip()

    if code in EXCEL_CODES:
        desc = EXCEL_CODES[code]
        gst = GST_RATES.get(code[:4])  # match 4-digit GST mapping
        return desc, gst

    if len(code) >= 4:
        short_code = code[:4]
        if short_code in EXCEL_CODES:
            desc = EXCEL_CODES[short_code]
            gst = GST_RATES.get(short_code)
            return desc, gst

    return None, None


# ---------- MAIN AUDIT ----------

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

    code_used = declared_hsn or declared_sac

    if code_used:
        desc, gst_rate = lookup_code(code_used)

        if desc:
            hsn_description = desc
            classification_source = f"Declared Code ({code_used})"
        else:
            reasons.append(f"Declared code {code_used} not found in Excel master")

        if gst_rate is not None:
            expected_gst = gst_rate
        else:
            reasons.append(f"No GST rate mapping found for code {code_used}")

    financial_discrepancy = False

    if billed_gst not in valid_slabs:
        financial_discrepancy = True
        reasons.append(f"GST {billed_gst}% not valid under {slab_type} regime")

    if code_used and expected_gst != billed_gst:
        if expected_gst is not None:
            financial_discrepancy = True
            reasons.append(
                f"GST applied {billed_gst}% but mapped rate is {expected_gst}%"
            )

    if abs(calculated_total - billed_total) > 1:
        financial_discrepancy = True
        reasons.append(
            f"Total mismatch. Expected ₹{calculated_total}, billed ₹{billed_total}"
        )

    overcharge = max(round(billed_total - calculated_total, 2), 0)

    if financial_discrepancy:
        status = "overcharged"
    elif reasons:
        status = "warning"
    else:
        status = "correct"

    if not reasons:
        reason_text = "Invoice is mathematically correct and GST slab valid."
    else:
        reason_text = " | ".join(reasons)

    return {
        "status": status,
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
        "expected_rate": billed_rate,
        "quantity": quantity,
        "reason": reason_text,
        "base_amount": base_amount,
        "gst_amount_expected": round(base_amount * expected_gst / 100, 2),
        "gst_amount_billed": gst_amount_billed
    }