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


# ---------- PDF TEXT EXTRACTION ----------

def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise Exception(f"Failed to read PDF: {str(e)}")
    return text


# ---------- SAFE JSON CLEANER ----------

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


# ---------- AI FIELD EXTRACTION ----------

def extract_invoice_fields(pdf_text):

    prompt = f"""
You are an Indian GST invoice structured data extractor.

STRICT RULES:
- Return ONLY valid JSON.
- No markdown.
- No explanation.
- No extra text.
- If field not found, return empty string or 0.

Extract the following fields:

- invoice_number (string)
- vendor_name (string)
- vendor_gstin (string)
- vendor_state (state name if visible else empty string)
- invoice_date (DD-MM-YYYY format if possible else empty string)
- invoice_total (number only)
- taxable_amount (number only)
- gst_amount (number only)
- gst_percent (number only)
- rate_per_unit (number only)
- quantity (number only)
- hsn_code (if explicitly mentioned else empty string)
- sac_code (if explicitly mentioned else empty string)

Invoice Text:
{pdf_text}

Return EXACTLY in this structure:

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
  "rate_per_unit": 0,
  "quantity": 0,
  "hsn_code": "",
  "sac_code": ""
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0
        )

        response_text = response.choices[0].message.content
        response_text = clean_json_response(response_text)

        data = json.loads(response_text)

        # ---------- NUMERIC SANITIZATION ----------

        numeric_fields = [
            "invoice_total",
            "taxable_amount",
            "gst_amount",
            "gst_percent",
            "rate_per_unit",
            "quantity"
        ]

        for key in numeric_fields:
            if key in data:
                if isinstance(data[key], str):
                    data[key] = re.sub(r"[^\d.]", "", data[key])
                try:
                    data[key] = float(data[key])
                except:
                    data[key] = 0.0

        # ---------- ENSURE ALL KEYS EXIST ----------

        required_fields = [
            "invoice_number",
            "vendor_name",
            "vendor_gstin",
            "vendor_state",
            "invoice_date",
            "invoice_total",
            "taxable_amount",
            "gst_amount",
            "gst_percent",
            "rate_per_unit",
            "quantity",
            "hsn_code",
            "sac_code"
        ]

        for field in required_fields:
            if field not in data:
                if field in numeric_fields:
                    data[field] = 0.0
                else:
                    data[field] = ""

        # ---------- HARD VALIDATION CLEANUP ----------

        # Clean invoice number
        data["invoice_number"] = str(data["invoice_number"]).strip()

        # Clean GSTIN (basic pattern check)
        gstin_pattern = r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[A-Z]{1}\d{1}"
        if not re.match(gstin_pattern, str(data["vendor_gstin"])):
            data["vendor_gstin"] = ""

        return data

    except json.JSONDecodeError:
        raise Exception("AI returned invalid JSON format.")
    except Exception as e:
        raise Exception(f"AI Extraction Error: {str(e)}")