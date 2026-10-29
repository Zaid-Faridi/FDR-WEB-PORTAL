"""
AICTE FDR Management Portal - Optical Character Recognition (OCR) Engine
Extracts FDR Number, Bank Name, Deposit Amount, and Dates from uploaded scans.
Powered by pytesseract with heuristic pattern normalization.
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger('aicte.ocr')

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract or PIL not installed. OCR will run in fallback heuristic mode.")

KNOWN_BANKS = [
    "State Bank of India",
    "Punjab National Bank",
    "Bank of Baroda",
    "Canara Bank",
    "Union Bank of India",
    "HDFC Bank",
    "ICICI Bank",
    "Axis Bank",
    "Kotak Mahindra Bank",
    "Central Bank of India",
    "Indian Bank",
    "Bank of India",
    "IndusInd Bank",
    "IDBI Bank",
]


def normalize_date_string(date_str: str) -> Optional[str]:
    """
    Attempts to parse various date formats (DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD)
    and formats as ISO standard YYYY-MM-DD.
    """
    if not date_str:
        return None
    cleaned = re.sub(r'[^0-9/\-.]', '', date_str.strip())
    delimiters = ['-', '/', '.']
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            # Normalize 2-digit years
            if dt.year < 1970:
                dt = dt.replace(year=dt.year + 100)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_amount_string(amt_str: str) -> Optional[float]:
    """
    Cleans and converts currency strings (e.g. '₹ 1,00,00,000.00' or 'Rs 5000000') to float.
    """
    if not amt_str:
        return None
    cleaned = re.sub(r'(?i)\b(?:rs|inr|rupees)\b\.?', '', amt_str.strip())
    cleaned = re.sub(r'[₹\s]', '', cleaned)
    if re.search(r'\.[0-9]{1,2}$', cleaned):
        parts = cleaned.rsplit('.', 1)
        int_part = re.sub(r'[^0-9]', '', parts[0])
        dec_part = parts[1]
        cleaned = f"{int_part}.{dec_part}"
    else:
        cleaned = re.sub(r'[^0-9]', '', cleaned)
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def extract_fdr_fields_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Rule-based regex entity extraction from raw text (OCR output or digital text).
    """
    extracted: Dict[str, Any] = {
        "reference_number": None,
        "bank_name": None,
        "amount": None,
        "issue_date": None,
        "maturity_date": None,
        "joint_holder": None,
        "raw_text": raw_text,
    }

    if not raw_text:
        return extracted

    # 1. Bank Name detection
    for bank in KNOWN_BANKS:
        pattern = re.compile(re.escape(bank), re.IGNORECASE)
        if pattern.search(raw_text):
            extracted["bank_name"] = bank
            break

    # 2. FDR / Reference Number detection
    ref_patterns = [
        r'(?:FDR|Receipt|Deposit|Certificate|Ref(?:erence)?)\s*(?:No\.?|Number|#)\s*[:.\s]+([A-Z0-9\-_/]{4,35})',
        r'Receipt\s*No\.?[:\s]+([A-Z0-9\-_/]{4,35})',
        r'(FDR-[A-Z0-9\-_]{4,25})',
    ]
    stopwords = {'RECEIPT', 'CERTIFICATE', 'DEPOSIT', 'BRANCH', 'BANK', 'NUMBER', 'AMOUNT', 'FIXED'}
    for p in ref_patterns:
        match = re.search(p, raw_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r'[,.;:]+$', '', candidate)
            if len(candidate) >= 4 and candidate.upper() not in stopwords and not candidate.lower().startswith('date'):
                extracted["reference_number"] = candidate
                break

    # 3. Amount extraction
    # Examples: "Amount: Rs. 1,00,00,000", "Principal Amount: ₹50,00,000.00"
    amount_patterns = [
        r'(?:Amount|Principal|Deposit Value|Sum of Rupees)[:\s]*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)',
        r'(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)',
        r'([0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}(?:\.[0-9]{2})?)',
    ]
    for p in amount_patterns:
        match = re.search(p, raw_text, re.IGNORECASE)
        if match:
            parsed = normalize_amount_string(match.group(1))
            if parsed and parsed >= 1000:  # Minimum realistic deposit
                extracted["amount"] = parsed
                break

    # 4. Issue Date extraction
    # Examples: "Issue Date: 15/01/2024", "Date of Deposit: 2024-01-15"
    issue_patterns = [
        r'(?:Issue Date|Date of Issue|Deposit Date|Effective Date)[:\s]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})',
        r'(?:Dated)[:\s]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})',
    ]
    for p in issue_patterns:
        match = re.search(p, raw_text, re.IGNORECASE)
        if match:
            normalized = normalize_date_string(match.group(1))
            if normalized:
                extracted["issue_date"] = normalized
                break

    # 5. Maturity Date extraction
    # Examples: "Maturity Date: 15/01/2034", "Due Date: 2034-01-15"
    maturity_patterns = [
        r'(?:Maturity Date|Due Date|Expiry Date|Date of Maturity)[:\s]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})',
        r'(?:Repayable on)[:\s]+([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})',
    ]
    for p in maturity_patterns:
        match = re.search(p, raw_text, re.IGNORECASE)
        if match:
            normalized = normalize_date_string(match.group(1))
            if normalized:
                extracted["maturity_date"] = normalized
                break

    # 6. Joint Holder / Lien keywords
    if re.search(r'AICTE|All India Council for Technical Education|Member Secretary', raw_text, re.IGNORECASE):
        extracted["joint_holder"] = "AICTE (Lien Mentioned)"

    return extracted


def extract_fdr_fields_from_file(file_obj_or_path, file_name: str = "") -> Dict[str, Any]:
    """
    Extracts text and key FDR fields from an uploaded document image or text file.
    Runs pytesseract on images (JPG, PNG). If PDF or plain text, extracts string content.
    """
    raw_text = ""
    ocr_engine = "heuristic_fallback"
    success = False

    name_lower = (file_name or getattr(file_obj_or_path, 'name', '')).lower()

    # Case A: Image processing with pytesseract
    if PYTESSERACT_AVAILABLE and any(name_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']):
        try:
            if hasattr(file_obj_or_path, 'read'):
                file_obj_or_path.seek(0)
                image = Image.open(file_obj_or_path)
            else:
                image = Image.open(file_obj_or_path)

            raw_text = pytesseract.image_to_string(image)
            ocr_engine = "pytesseract-5.x"
            success = bool(raw_text.strip())
        except Exception as exc:
            logger.warning("Pytesseract extraction failed: %s. Using heuristic fallback.", exc)
            raw_text = ""

    # Case B: Plain text / Simulated file read or fallback
    if not raw_text.strip():
        try:
            if hasattr(file_obj_or_path, 'read'):
                file_obj_or_path.seek(0)
                content = file_obj_or_path.read()
                if isinstance(content, bytes):
                    # Try utf-8 or ascii decode
                    try:
                        raw_text = content.decode('utf-8', errors='ignore')
                    except Exception:
                        raw_text = ""
                elif isinstance(content, str):
                    raw_text = content
            elif isinstance(file_obj_or_path, str):
                with open(file_obj_or_path, 'r', errors='ignore') as f:
                    raw_text = f.read()
        except Exception as exc:
            logger.debug("Raw file read attempt failed: %s", exc)

    extracted = extract_fdr_fields_from_text(raw_text)
    extracted["ocr_engine"] = ocr_engine
    extracted["success"] = bool(extracted["reference_number"] or extracted["amount"] or extracted["bank_name"])
    return extracted


def compare_ocr_vs_typed(ocr_data: Dict[str, Any], typed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compares OCR extracted fields against user typed values and returns list of discrepancies.
    """
    mismatches = []
    if not ocr_data or not ocr_data.get("success"):
        return mismatches

    # 1. Reference Number
    ocr_ref = ocr_data.get("reference_number")
    typed_ref = typed_data.get("reference_number")
    if ocr_ref and typed_ref:
        if re.sub(r'[^A-Za-z0-9]', '', ocr_ref).upper() != re.sub(r'[^A-Za-z0-9]', '', typed_ref).upper():
            mismatches.append({
                "field": "reference_number",
                "label": "FDR Number",
                "ocr_value": ocr_ref,
                "typed_value": typed_ref,
                "message": f"Scan OCR read '{ocr_ref}' but institution entered '{typed_ref}'."
            })

    # 2. Bank Name
    ocr_bank = ocr_data.get("bank_name")
    typed_bank = typed_data.get("issuing_bank") or typed_data.get("bank_name")
    if ocr_bank and typed_bank:
        if ocr_bank.lower() not in typed_bank.lower() and typed_bank.lower() not in ocr_bank.lower():
            mismatches.append({
                "field": "issuing_bank",
                "label": "Issuing Bank",
                "ocr_value": ocr_bank,
                "typed_value": typed_bank,
                "message": f"Scan indicates bank '{ocr_bank}' but institution entered '{typed_bank}'."
            })

    # 3. Amount
    ocr_amt = ocr_data.get("amount")
    typed_amt = typed_data.get("amount")
    if ocr_amt is not None and typed_amt is not None:
        try:
            t_amt = float(typed_amt)
            if abs(ocr_amt - t_amt) > 1.0:
                mismatches.append({
                    "field": "amount",
                    "label": "Deposit Amount",
                    "ocr_value": f"₹{ocr_amt:,.2f}",
                    "typed_value": f"₹{t_amt:,.2f}",
                    "message": f"Scan OCR detected ₹{ocr_amt:,.2f} while typed amount is ₹{t_amt:,.2f}."
                })
        except (ValueError, TypeError):
            pass

    # 4. Dates
    for date_field, label in [("issue_date", "Issue Date"), ("maturity_date", "Maturity Date")]:
        ocr_d = ocr_data.get(date_field)
        typed_d = str(typed_data.get(date_field) or "")
        if ocr_d and typed_d and ocr_d != typed_d:
            mismatches.append({
                "field": date_field,
                "label": label,
                "ocr_value": ocr_d,
                "typed_value": typed_d,
                "message": f"Scan indicates {label} as {ocr_d} but institution entered {typed_d}."
            })

    return mismatches
