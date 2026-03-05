# risk_engine.py

def detect_exact_duplicate(invoice_number, history):
    return any(inv["invoice_number"] == invoice_number for inv in history)


def detect_vendor_amount_duplicate(vendor, amount, history):
    return any(
        inv["vendor"] == vendor and inv["amount"] == amount
        for inv in history
    )


def detect_suspicious_rounding(amount):
    amount_str = str(int(amount)) if amount == int(amount) else str(amount)

    if amount % 1000 == 0:
        return True

    if amount_str.endswith(("00", "99", "50")):
        return True

    return False


def detect_rate_spike(vendor, amount, history):
    vendor_amounts = [
        inv["amount"] for inv in history if inv["vendor"] == vendor
    ]

    if len(vendor_amounts) < 2:
        return False, 0

    avg = sum(vendor_amounts) / len(vendor_amounts)

    if amount > avg * 1.3:
        spike_percent = ((amount - avg) / avg) * 100
        return True, round(spike_percent, 2)

    return False, 0