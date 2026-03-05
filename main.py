import os
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import pandas as pd
import io

from core.extractor import extract_text_from_pdf, extract_invoice_fields
from core.auditor import audit_invoice
from core.risk_engine import (
    detect_exact_duplicate,
    detect_vendor_amount_duplicate,
    detect_suspicious_rounding,
    detect_rate_spike,
)

load_dotenv()

app = FastAPI(title="AI Invoice Auditor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (per-process; fine for single-user Render free tier)
invoice_history: list = []
money_saved: float = 0.0

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/api/dashboard")
def get_dashboard():
    total_invoices = len(invoice_history)
    total_billed = sum(inv["amount"] for inv in invoice_history)
    fail_count = sum(1 for inv in invoice_history if inv["status"] == "FAIL")
    warning_count = sum(1 for inv in invoice_history if inv["status"] == "WARNING")
    return {
        "total_invoices": total_invoices,
        "total_billed": total_billed,
        "money_saved": money_saved,
        "fail_count": fail_count,
        "warning_count": warning_count,
        "history": invoice_history,
    }


@app.post("/api/audit")
async def audit(
    file: UploadFile = File(...),
    buyer_gstin: str = Form(default="27ABCDE1234F1Z5"),
):
    global money_saved

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()
    pdf_file = io.BytesIO(pdf_bytes)

    # Step 1 — Extract text
    pdf_text = extract_text_from_pdf(pdf_file)
    if not pdf_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text. Use a text-based PDF.")

    # Step 2 — AI field extraction
    fields = extract_invoice_fields(pdf_text)

    # Step 3 — Core audit
    result = audit_invoice(fields, buyer_gstin)

    invoice_number = fields.get("invoice_number", "")
    vendor = result.get("vendor", "")
    amount = result.get("billed_total", 0)

    # Phase 1 Intelligence
    if invoice_number and detect_exact_duplicate(invoice_number, invoice_history):
        result["issues"].append({
            "type": "CRITICAL",
            "message": "Exact duplicate invoice detected.",
            "impact": 0,
        })
        result["status"] = "FAIL"
        result["recommendation"] = "REJECT"
    elif detect_vendor_amount_duplicate(vendor, amount, invoice_history):
        result["issues"].append({
            "type": "WARNING",
            "message": "Repeated identical billing detected.",
            "impact": 0,
        })
        if result["status"] == "PASS":
            result["status"] = "WARNING"
            result["recommendation"] = "REVIEW"

    if detect_suspicious_rounding(amount):
        result["issues"].append({
            "type": "WARNING",
            "message": "Suspicious rounding pattern detected.",
            "impact": 0,
        })

    spike_detected, spike_percent = detect_rate_spike(vendor, amount, invoice_history)
    if spike_detected:
        result["issues"].append({
            "type": "WARNING",
            "message": f"Invoice amount {spike_percent}% higher than vendor average.",
            "impact": 0,
        })

    # Money saved
    total_impact = sum(issue.get("impact", 0) for issue in result["issues"])
    money_saved += total_impact

    # Risk score
    risk_score = 0
    for issue in result["issues"]:
        if issue["type"] == "CRITICAL":
            risk_score += 30
        elif issue["type"] == "WARNING":
            risk_score += 10
    risk_score = min(risk_score, 100)

    # Store history
    invoice_history.append({
        "invoice_number": invoice_number,
        "vendor": vendor,
        "amount": amount,
        "status": result["status"],
    })

    return {
        "fields": fields,
        "result": result,
        "risk_score": risk_score,
        "total_impact": total_impact,
    }


@app.post("/api/reset")
def reset_session():
    global invoice_history, money_saved
    invoice_history = []
    money_saved = 0.0
    return {"message": "Session reset."}
