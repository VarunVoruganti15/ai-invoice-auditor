import pdfplumber
import json
import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=api_key)


# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------
def extract_text_from_pdf(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


# -----------------------------
# CLEAN JSON RESPONSE
# -----------------------------
def clean_json_response(response_text):
    response_text = response_text.strip()
    if "```" in response_text:
        parts = response_text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                return part
    return response_text


# -----------------------------
# AI EXTRACTION
# -----------------------------
def extract_invoice_fields(pdf_text):

    prompt = f"""
You are an Indian GST invoice structured extractor.

STRICT RULES:
- Return ONLY valid JSON.
- No explanation.
- If field missing → return empty string or 0.

Extract:

- invoice_number
- vendor_name
- vendor_gstin
- vendor_state
- invoice_date
- invoice_total
- taxable_amount
- gst_amount
- gst_percent
- cgst_amount
- sgst_amount
- igst_amount
- rate_per_unit
- quantity
- hsn_code
- sac_code

Invoice Text:
{pdf_text}

Return EXACT JSON:

{{
  "invoice_number": "",
  "vendor_name": "",
  "vendor_gstin": "",
  "vendor_state": "",
  "invoice_date": "",
  "invoice_total": 0,
  "taxable_amount": 0,
  "gst_amount": 0,
  "gst_percent": 0,
  "cgst_amount": 0,
  "sgst_amount": 0,
  "igst_amount": 0,
  "rate_per_unit": 0,
  "quantity": 0,
  "hsn_code": "",
  "sac_code": ""
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=800
    )

    response_text = clean_json_response(response.choices[0].message.content)
    data = json.loads(response_text)

    numeric_fields = [
        "invoice_total",
        "taxable_amount",
        "gst_amount",
        "gst_percent",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "rate_per_unit",
        "quantity"
    ]

    for field in numeric_fields:
        value = data.get(field, 0)
        if isinstance(value, str):
            value = re.sub(r"[^\d.]", "", value)
        try:
            data[field] = float(value)
        except:
            data[field] = 0.0

    return data