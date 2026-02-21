import json
import os


def load_contract():
    contract_path = os.path.join(os.path.dirname(__file__), "contract.json")
    with open(contract_path, "r") as f:
        return json.load(f)


def detect_hsn_category(vendor_name, pdf_text=""):
    """
    Detect HSN code and correct GST rate for ANY Indian invoice
    by matching keywords from vendor name and invoice text
    """
    contract = load_contract()
    hsn_codes = contract.get("hsn_codes", {})

    search_text = (vendor_name + " " + pdf_text).lower()

    best_hsn = None
    best_description = "General Services"
    best_gst = 18
    best_score = 0

    for hsn, data in hsn_codes.items():
        keywords = data.get("keywords", [])
        score = 0
        for keyword in keywords:
            if keyword.lower() in search_text:
                # Longer keyword match = more specific = higher score
                score += len(keyword.split())
        if score > best_score:
            best_score = score
            best_hsn = hsn
            best_description = data["description"]
            best_gst = data["gst_percent"]

    if not best_hsn:
        best_hsn = "9983"
        best_description = "General Services"
        best_gst = 18

    return best_hsn, best_description, best_gst


def audit_invoice(extracted_fields, pdf_text=""):
    """
    Universal audit for ANY Indian invoice.
    Uses HSN codes and 2026 GST slab rates.
    Works for every company and every invoice type.
    """
    # 2026 Updated Indian GST Slabs
    valid_gst_slabs = [0, 3, 5, 12, 18, 40]

    vendor = extracted_fields.get("vendor_name", "").strip()
    billed_total = float(extracted_fields.get("invoice_total", 0))
    billed_gst = float(extracted_fields.get("gst_percent", 0))
    billed_rate = float(extracted_fields.get("rate_per_unit", 0))
    quantity = float(extracted_fields.get("quantity", 0))

    # Detect HSN code and correct GST for this vendor/invoice
    hsn_code, hsn_description, expected_gst = detect_hsn_category(vendor, pdf_text)

    base_amount = round(billed_rate * quantity, 2)
    expected_total = round(base_amount + (base_amount * expected_gst / 100), 2)
    overcharge = round(billed_total - expected_total, 2)

    reasons = []

    # Check 1 — Is GST slab valid per 2026 rules?
    if billed_gst not in valid_gst_slabs:
        nearest_slab = min(valid_gst_slabs, key=lambda x: abs(x - billed_gst))
        reasons.append(
            f"GST {billed_gst}% is not a valid 2026 Indian GST slab "
            f"(Valid slabs: 0%, 3%, 5%, 12%, 18%, 40%). "
            f"Nearest valid slab: {nearest_slab}%"
        )
        corrected_total = round(base_amount + (base_amount * nearest_slab / 100), 2)
        overcharge = round(billed_total - corrected_total, 2)
        expected_total = corrected_total
        expected_gst = nearest_slab

    # Check 2 — Is GST rate correct for this HSN category?
    elif billed_gst != expected_gst:
        reasons.append(
            f"GST applied {billed_gst}% but HSN {hsn_code} "
            f"({hsn_description}) should attract {expected_gst}% "
            f"as per 2026 GST rules"
        )

    # Check 3 — Does the invoice math add up?
    if abs(overcharge) > 1 and not reasons:
        reasons.append(
            f"Invoice total Rs{billed_total} doesn't match "
            f"calculated total Rs{expected_total} "
            f"(rate × qty + GST = Rs{base_amount} + {billed_gst}% = Rs{expected_total})"
        )

    if not reasons and abs(overcharge) <= 1:
        return {
            "status": "correct",
            "vendor": vendor,
            "hsn_code": hsn_code,
            "hsn_description": hsn_description,
            "billed_total": billed_total,
            "expected_total": expected_total,
            "overcharge": 0,
            "billed_gst": billed_gst,
            "expected_gst": expected_gst,
            "billed_rate": billed_rate,
            "expected_rate": billed_rate,
            "quantity": quantity,
            "reason": (
                f"Invoice is correct. GST {billed_gst}% is valid for "
                f"HSN {hsn_code} — {hsn_description}."
            ),
            "base_amount": base_amount,
            "gst_amount_expected": round(base_amount * expected_gst / 100, 2),
            "gst_amount_billed": round(base_amount * billed_gst / 100, 2)
        }
    else:
        return {
            "status": "overcharged",
            "vendor": vendor,
            "hsn_code": hsn_code,
            "hsn_description": hsn_description,
            "billed_total": billed_total,
            "expected_total": expected_total,
            "overcharge": max(overcharge, 0),
            "billed_gst": billed_gst,
            "expected_gst": expected_gst,
            "billed_rate": billed_rate,
            "expected_rate": billed_rate,
            "quantity": quantity,
            "reason": " | ".join(reasons),
            "base_amount": base_amount,
            "gst_amount_expected": round(base_amount * expected_gst / 100, 2),
            "gst_amount_billed": round(base_amount * billed_gst / 100, 2)
        }