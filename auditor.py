import json
import os


def load_contract():
    contract_path = os.path.join(os.path.dirname(__file__), "contract.json")
    with open(contract_path, "r") as f:
        return json.load(f)


def find_best_vendor_match(vendor_name, contract):
    """Smart vendor matching — handles partial names, abbreviations, typos"""
    vendor_lower = vendor_name.lower().strip()

    # 1. Exact match first
    for contract_vendor in contract.keys():
        if contract_vendor.lower() == vendor_lower:
            return contract_vendor

    # 2. One contains the other
    for contract_vendor in contract.keys():
        cv_lower = contract_vendor.lower()
        if cv_lower in vendor_lower or vendor_lower in cv_lower:
            return contract_vendor

    # 3. Word by word match — if 2+ words match
    vendor_words = set(vendor_lower.split())
    best_match = None
    best_score = 0
    for contract_vendor in contract.keys():
        cv_words = set(contract_vendor.lower().split())
        common_words = vendor_words & cv_words
        # Ignore common filler words
        filler = {"ltd", "limited", "pvt", "private", "india", "the", "and", "&", "co", "inc"}
        meaningful_common = common_words - filler
        if len(meaningful_common) >= 2 and len(meaningful_common) > best_score:
            best_score = len(meaningful_common)
            best_match = contract_vendor

    if best_match:
        return best_match

    # 4. First significant word match
    significant_vendor_words = [w for w in vendor_lower.split() if len(w) > 3]
    for contract_vendor in contract.keys():
        cv_lower = contract_vendor.lower()
        for word in significant_vendor_words:
            if word in cv_lower:
                return contract_vendor

    return None


def audit_invoice(extracted_fields):
    contract = load_contract()

    vendor = extracted_fields.get("vendor_name", "").strip()
    billed_total = float(extracted_fields.get("invoice_total", 0))
    billed_gst = float(extracted_fields.get("gst_percent", 0))
    billed_rate = float(extracted_fields.get("rate_per_unit", 0))
    quantity = float(extracted_fields.get("quantity", 0))

    matched_vendor = find_best_vendor_match(vendor, contract)

    if not matched_vendor:
        # Smart fallback — audit using GST rules even if vendor unknown
        return audit_by_gst_rules_only(
            vendor, billed_total, billed_gst, billed_rate, quantity
        )

    contract_data = contract[matched_vendor]
    expected_gst = float(contract_data["gst_percent"])
    expected_rate = float(contract_data["rate_per_unit"])

    base_amount = expected_rate * quantity
    expected_total = round(base_amount + (base_amount * expected_gst / 100), 2)
    overcharge = round(billed_total - expected_total, 2)

    reasons = []
    if billed_gst != expected_gst:
        reasons.append(f"GST applied {billed_gst}% instead of contracted {expected_gst}%")
    if billed_rate != expected_rate:
        reasons.append(f"Rate charged Rs{billed_rate}/unit instead of contracted Rs{expected_rate}/unit")

    if overcharge <= 0 and not reasons:
        status = "correct"
        reason_text = "All values match the contract. Invoice is verified correct."
        overcharge = 0
    else:
        status = "overcharged"
        reason_text = " | ".join(reasons) if reasons else "Total amount does not match contract value."

    return {
        "status": status,
        "vendor": matched_vendor,
        "extracted_vendor": vendor,
        "billed_total": billed_total,
        "expected_total": expected_total,
        "overcharge": max(overcharge, 0),
        "billed_gst": billed_gst,
        "expected_gst": expected_gst,
        "billed_rate": billed_rate,
        "expected_rate": expected_rate,
        "quantity": quantity,
        "reason": reason_text,
        "base_amount": round(base_amount, 2),
        "gst_amount_expected": round(base_amount * expected_gst / 100, 2),
        "gst_amount_billed": round((billed_rate * quantity) * billed_gst / 100, 2)
    }


def audit_by_gst_rules_only(vendor, billed_total, billed_gst, billed_rate, quantity):
    """
    Fallback audit using India GST slab rules when vendor not in contract.
    Checks if GST applied is a valid Indian GST slab: 0, 5, 12, 18, 28
    """
    valid_gst_slabs = [0, 5, 12, 18, 28]

    if billed_gst not in valid_gst_slabs:
        base_amount = billed_rate * quantity
        # Find nearest valid slab
        nearest_slab = min(valid_gst_slabs, key=lambda x: abs(x - billed_gst))
        expected_total = round(base_amount + (base_amount * nearest_slab / 100), 2)
        overcharge = round(billed_total - expected_total, 2)
        return {
            "status": "overcharged",
            "vendor": vendor,
            "extracted_vendor": vendor,
            "billed_total": billed_total,
            "expected_total": expected_total,
            "overcharge": max(overcharge, 0),
            "billed_gst": billed_gst,
            "expected_gst": nearest_slab,
            "billed_rate": billed_rate,
            "expected_rate": billed_rate,
            "quantity": quantity,
            "reason": f"GST {billed_gst}% is not a valid Indian GST slab. Nearest valid slab is {nearest_slab}%",
            "base_amount": round(base_amount, 2),
            "gst_amount_expected": round(base_amount * nearest_slab / 100, 2),
            "gst_amount_billed": round(base_amount * billed_gst / 100, 2)
        }

    # GST slab is valid, do basic math check
    base_amount = billed_rate * quantity
    recalculated_total = round(base_amount + (base_amount * billed_gst / 100), 2)
    overcharge = round(billed_total - recalculated_total, 2)

    if abs(overcharge) <= 1:  # Allow Rs1 rounding difference
        return {
            "status": "correct",
            "vendor": vendor,
            "extracted_vendor": vendor,
            "billed_total": billed_total,
            "expected_total": recalculated_total,
            "overcharge": 0,
            "billed_gst": billed_gst,
            "expected_gst": billed_gst,
            "billed_rate": billed_rate,
            "expected_rate": billed_rate,
            "quantity": quantity,
            "reason": "Invoice math is correct. GST slab is valid. Note: Vendor not in contract database.",
            "base_amount": round(base_amount, 2),
            "gst_amount_expected": round(base_amount * billed_gst / 100, 2),
            "gst_amount_billed": round(base_amount * billed_gst / 100, 2)
        }
    else:
        return {
            "status": "overcharged",
            "vendor": vendor,
            "extracted_vendor": vendor,
            "billed_total": billed_total,
            "expected_total": recalculated_total,
            "overcharge": max(overcharge, 0),
            "billed_gst": billed_gst,
            "expected_gst": billed_gst,
            "billed_rate": billed_rate,
            "expected_rate": billed_rate,
            "quantity": quantity,
            "reason": f"Invoice total Rs{billed_total} doesn't match calculated total Rs{recalculated_total} based on given rate and GST.",
            "base_amount": round(base_amount, 2),
            "gst_amount_expected": round(base_amount * billed_gst / 100, 2),
            "gst_amount_billed": round(base_amount * billed_gst / 100, 2)
        }