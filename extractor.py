import pdfplumber
import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=api_key)


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


def extract_invoice_fields(pdf_text):
    prompt = f"""
You are a professional invoice data extractor.
Read the invoice text below and extract key fields.
Return ONLY a valid JSON object. No explanation. No markdown. Just JSON.

Fields to extract:
- vendor_name (string)
- invoice_total (number only, no currency symbol)
- gst_percent (number only)
- rate_per_unit (number only)
- quantity (number only)

Invoice Text:
{pdf_text}

Return ONLY this format:
{{
  "vendor_name": "ABC Logistics",
  "invoice_total": 12480,
  "gst_percent": 18,
  "rate_per_unit": 50,
  "quantity": 200
}}
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0
        )

        response_text = response.choices[0].message.content.strip()

        if "```" in response_text:
            parts = response_text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    response_text = part
                    break

        return json.loads(response_text)

    except json.JSONDecodeError:
        raise Exception("AI returned invalid format. Please try again.")
    except Exception as e:
        raise Exception(f"AI Extraction Error: {str(e)}")