import datetime
import json
import os

# -----------------------------
# GST STATE CODE MAPPING
# -----------------------------
GST_STATE_CODES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "36": "Telangana",
    "37": "Andhra Pradesh"
}


def get_state_from_gstin(gstin):
    if gstin and len(gstin) >= 2:
        return GST_STATE_CODES.get(gstin[:2], "")
    return ""


def safe_float(value):
    try:
        return float(value)
    except:
        return 0.0


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


def audit_invoice(extracted_fields, buyer_gstin, vendor_master: dict = None):

    vendor = extracted_fields.get("vendor_name", "")
    invoice_date = extracted_fields.get("invoice_date", "")

    buyer_state = get_state_from_gstin(buyer_gstin)
    vendor_state = extracted_fields.get("vendor_state", "").strip()

    # --- Vendor Master Lookup (Priority 1: GSTIN, Priority 2: Name) ---
    vendor_master_record = None
    vendor_master_matched = False
    match_method = None

    if vendor_master:
        by_gstin = vendor_master.get("by_gstin", {})
        by_name = vendor_master.get("by_name", {})

        # Extract vendor GSTIN from invoice fields for matching
        invoice_vendor_gstin = extracted_fields.get("vendor_gstin", "").strip()

        # Priority 1 — Match by GSTIN (most reliable)
        if invoice_vendor_gstin and invoice_vendor_gstin in by_gstin:
            vendor_master_record = by_gstin[invoice_vendor_gstin]
            vendor_master_matched = True
            match_method = "GSTIN"
        else:
            # Priority 2 — Fallback: match by vendor name
            name_key = vendor.lower().strip()
            if name_key in by_name:
                vendor_master_record = by_name[name_key]
                vendor_master_matched = True
                match_method = "name"

        if vendor_master_record:
            # Override with authoritative master state
            if vendor_master_record.get("state"):
                vendor_state = vendor_master_record["state"].strip()
            # Derive state from master GSTIN if state field is blank
            if not vendor_state and vendor_master_record.get("gstin"):
                vendor_state = get_state_from_gstin(vendor_master_record["gstin"])

    billed_total = safe_float(extracted_fields.get("invoice_total"))
    taxable_amount = safe_float(extracted_fields.get("taxable_amount"))
    billed_gst_percent = safe_float(extracted_fields.get("gst_percent"))

    cgst = safe_float(extracted_fields.get("cgst_amount"))
    sgst = safe_float(extracted_fields.get("sgst_amount"))
    igst = safe_float(extracted_fields.get("igst_amount"))

    rate = safe_float(extracted_fields.get("rate_per_unit"))
    quantity = safe_float(extracted_fields.get("quantity"))

    valid_slabs, slab_type = get_valid_slabs(invoice_date)

    issues = []

    base_amount = taxable_amount if taxable_amount > 0 else rate * quantity
    base_amount = round(base_amount, 2)

    total_gst_billed = round(cgst + sgst + igst, 2)
    calculated_total = round(base_amount + total_gst_billed, 2)

    # -----------------------------
    # GST SLAB VALIDATION
    # -----------------------------
    if billed_gst_percent not in valid_slabs:
        issues.append({
            "type": "CRITICAL",
            "message": f"GST {billed_gst_percent}% invalid under {slab_type} regime.",
            "impact": 0
        })

    # -----------------------------
    # GST STRUCTURE VALIDATION
    # -----------------------------
    if buyer_state and vendor_state:
        same_state = vendor_state.lower() == buyer_state.lower()

        if same_state:
            if igst > 0:
                issues.append({
                    "type": "CRITICAL",
                    "message": "IGST applied for intra-state transaction.",
                    "impact": 0
                })
            if cgst == 0 or sgst == 0:
                issues.append({
                    "type": "CRITICAL",
                    "message": "CGST and SGST required for intra-state transaction.",
                    "impact": 0
                })
        else:
            if igst == 0:
                issues.append({
                    "type": "CRITICAL",
                    "message": "IGST required for inter-state transaction.",
                    "impact": 0
                })
            if cgst > 0 or sgst > 0:
                issues.append({
                    "type": "CRITICAL",
                    "message": "CGST/SGST applied for inter-state transaction.",
                    "impact": 0
                })

    # -----------------------------
    # GST PERCENT VALIDATION
    # -----------------------------
    expected_gst_amount = round(base_amount * billed_gst_percent / 100, 2)

    if abs(total_gst_billed - expected_gst_amount) > 1:
        issues.append({
            "type": "CRITICAL",
            "message": "GST breakup does not match GST percentage.",
            "impact": 0
        })

    # -----------------------------
    # TOTAL VALIDATION
    # -----------------------------
    if abs(calculated_total - billed_total) > 1:
        impact = max(round(billed_total - calculated_total, 2), 0)
        issues.append({
            "type": "CRITICAL",
            "message": "Invoice total mismatch.",
            "impact": impact
        })

    overcharge = max(round(billed_total - calculated_total, 2), 0)

    # -----------------------------
    # VENDOR MASTER VALIDATION
    # -----------------------------
    if vendor_master and not vendor_master_matched:
        issues.append({
            "type": "WARNING",
            "message": f"Vendor '{vendor}' not found in the uploaded Vendor Master. State/GSTIN from invoice used.",
            "impact": 0
        })

    status = "FAIL" if any(i["type"] == "CRITICAL" for i in issues) else "PASS"
    if status == "PASS" and any(i["type"] == "WARNING" for i in issues):
        status = "WARNING"
    recommendation = "REJECT" if status == "FAIL" else ("REVIEW" if status == "WARNING" else "PAY")

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
        "buyer_state": buyer_state,
        "vendor_state": vendor_state,
        "billed_total": billed_total,
        "expected_total": calculated_total,
        "overcharge": overcharge,
        "issues": issues,
        "base_amount": base_amount,
        "vendor_master_matched": vendor_master_matched,
        "vendor_match_method": match_method,
        "vendor_payment_terms": vendor_master_record.get("payment_terms", "") if vendor_master_record else "",
    }