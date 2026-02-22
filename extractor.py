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
You are an Indian GST invoice data extractor.

Read the invoice text and extract ONLY the required structured data.

Return ONLY valid JSON.
No explanation.
No markdown.
No extra text.

Fields:
- vendor_name (string)
- invoice_date (DD-MM-YYYY format if available, else empty string)
- invoice_total (number only, no currency symbol)
- gst_percent (number only)
- rate_per_unit (number only)
- quantity (number only)
- hsn_code (if explicitly mentioned, else empty string)
- sac_code (if explicitly mentioned, else empty string)

Invoice Text:
{pdf_text}

Return EXACTLY this format:

{{
  "vendor_name": "ABC Logistics",
  "invoice_date": "21-09-2025",
  "invoice_total": 12480,
  "gst_percent": 18,
  "rate_per_unit": 50,
  "quantity": 200,
  "hsn_code": "",
  "sac_code": ""
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0
        )

        response_text = response.choices[0].message.content
        response_text = clean_json_response(response_text)

        data = json.loads(response_text)

        # ---- Sanitize numeric fields ----
        for key in ["invoice_total", "gst_percent", "rate_per_unit", "quantity"]:
            if key in data:
                if isinstance(data[key], str):
                    data[key] = re.sub(r"[^\d.]", "", data[key])
                try:
                    data[key] = float(data[key])
                except:
                    data[key] = 0.0

        # Ensure missing keys exist
        for field in [
            "vendor_name",
            "invoice_date",
            "invoice_total",
            "gst_percent",
            "rate_per_unit",
            "quantity",
            "hsn_code",
            "sac_code"
        ]:
            if field not in data:
                data[field] = "" if "code" in field or "date" in field else 0

        return data

    except json.JSONDecodeError:
        raise Exception("AI returned invalid JSON format.")
    except Exception as e:
        raise Exception(f"AI Extraction Error: {str(e)}")