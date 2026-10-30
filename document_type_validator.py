"""
Document Type Validator for OnboardAI.

Detects the likely document type from extracted text using multi-indicator
rule-based analysis and optional AI classification via Ollama/Gemma.
Compares detected type against the user-selected document category
and returns a validation result.

IMPORTANT:
- This module does NOT perform government identity verification.
- It performs preliminary content-based type matching only.
- HR approval remains the final review step.
- Sensitive identifiers (Aadhaar, PAN) are masked in outputs.
"""

import re
from typing import Dict, Any, Tuple, Optional
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

# ---------------------------------------------------------------------------
# Validation result statuses
# ---------------------------------------------------------------------------
STATUS_MATCHED = "Type Matched"
STATUS_MISMATCH = "Type Mismatch"
STATUS_INCONCLUSIVE = "Inconclusive"
STATUS_AWAITING_REVIEW = "Awaiting HR Review"

# ---------------------------------------------------------------------------
# Categories that require strict type validation
# ---------------------------------------------------------------------------
VALIDATED_CATEGORIES = [
    "Aadhaar Card",
    "PAN Card",
    "Passport",
    "Driving Licence",
    "Educational Certificate",
]

# Categories that skip strict type validation (generic buckets)
GENERIC_CATEGORIES = [
    "Resume / CV",
    "Government ID / Passport",
    "Offer Letter",
    "Educational Degree / Transcript",
    "Direct Deposit / Bank Form",
    "Other Supporting Documents",
]


# ---------------------------------------------------------------------------
# Masking helpers (security & privacy)
# ---------------------------------------------------------------------------
def mask_aadhaar(number: str) -> str:
    """Mask an Aadhaar number showing only last 4 digits."""
    digits = re.sub(r'\D', '', number)
    if len(digits) >= 8:
        return "XXXX-XXXX-" + digits[-4:]
    return "XXXX-XXXX-XXXX"


def mask_pan(pan: str) -> str:
    """Mask a PAN number showing only last 3 characters."""
    pan = pan.strip().upper()
    if len(pan) >= 5:
        return "XXXXX" + pan[-5:][:2] + "XX" + pan[-1:]
    return "XXXXXXXXXX"


# ---------------------------------------------------------------------------
# Indicator detection functions — each returns (score, evidence_list)
# ---------------------------------------------------------------------------

def _detect_aadhaar_indicators(text: str) -> Tuple[int, list]:
    """Detect Aadhaar Card indicators from document text."""
    score = 0
    evidence = []
    upper_text = text.upper()

    # Heading / label indicators
    aadhaar_labels = [
        r'\bAADHAAR\b', r'\bUIDAI\b', r'\bUNIQUE\s*IDENTIFICATION\b',
        r'\bENROLMENT\s*(?:NO|NUMBER|ID)\b', r'\bVID\b',
        r'\bGOVERNMENT\s*OF\s*INDIA\b', r'\bMALE\b|\bFEMALE\b',
        r'\bDATE\s*OF\s*BIRTH\b', r'\bDOB\b', r'\bADDRESS\b',
    ]
    for pattern in aadhaar_labels:
        if re.search(pattern, upper_text):
            score += 2
            evidence.append(f"Label match: {pattern}")

    # 12-digit number pattern (with or without spaces/dashes)
    aadhaar_nums = re.findall(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', text)
    for num in aadhaar_nums:
        digits = re.sub(r'\D', '', num)
        if len(digits) == 12:
            score += 5
            evidence.append(f"12-digit number: {mask_aadhaar(digits)}")
            break  # one is enough

    # Negative: PAN-like patterns reduce score
    pan_patterns = re.findall(r'\b[A-Z]{5}\d{4}[A-Z]\b', text.upper())
    if pan_patterns:
        score -= 3

    return max(score, 0), evidence


def _detect_pan_indicators(text: str) -> Tuple[int, list]:
    """Detect PAN Card indicators from document text."""
    score = 0
    evidence = []
    upper_text = text.upper()

    # Label indicators
    pan_labels = [
        r'\bPAN\b', r'\bPERMANENT\s*ACCOUNT\s*NUMBER\b',
        r'\bINCOME\s*TAX\b', r'\bDEPARTMENT\b',
        r'\bGOVT\.?\s*OF\s*INDIA\b', r"\bFATHER'?S?\s*NAME\b",
        r'\bDATE\s*OF\s*BIRTH\b', r'\bSIGNATURE\b',
    ]
    for pattern in pan_labels:
        if re.search(pattern, upper_text):
            score += 2
            evidence.append(f"Label match: {pattern}")

    # PAN format: ABCDE1234F (5 alpha + 4 digit + 1 alpha)
    pan_matches = re.findall(r'\b[A-Z]{5}\d{4}[A-Z]\b', upper_text)
    if pan_matches:
        score += 6
        evidence.append(f"PAN pattern: {mask_pan(pan_matches[0])}")

    # Negative: 12-digit Aadhaar-like numbers reduce score
    aadhaar_nums = re.findall(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', text)
    for num in aadhaar_nums:
        digits = re.sub(r'\D', '', num)
        if len(digits) == 12:
            score -= 3
            break

    return max(score, 0), evidence


def _detect_passport_indicators(text: str) -> Tuple[int, list]:
    """Detect Passport indicators from document text."""
    score = 0
    evidence = []
    upper_text = text.upper()

    passport_labels = [
        r'\bPASSPORT\b', r'\bREPUBLIC\s*OF\s*INDIA\b',
        r'\bNATIONALITY\b', r'\bPLACE\s*OF\s*(?:BIRTH|ISSUE)\b',
        r'\bDATE\s*OF\s*(?:ISSUE|EXPIRY)\b', r'\bSURNAME\b',
        r'\bGIVEN\s*NAME\b', r'\bPASSPORT\s*NO\b',
        r'\bTYPE\b.*\bCOUNTRY\s*CODE\b', r'\bMRZ\b',
    ]
    for pattern in passport_labels:
        if re.search(pattern, upper_text):
            score += 2
            evidence.append(f"Label match: {pattern}")

    # Passport number pattern (alpha + digits, ~8 chars)
    passport_nums = re.findall(r'\b[A-Z]\d{7}\b', upper_text)
    if passport_nums:
        score += 4
        evidence.append(f"Passport number pattern found")

    # MRZ-like lines (two long lines of uppercase + < characters)
    mrz_lines = re.findall(r'[A-Z<]{30,}', upper_text)
    if mrz_lines:
        score += 4
        evidence.append("MRZ-like line detected")

    return max(score, 0), evidence


def _detect_driving_licence_indicators(text: str) -> Tuple[int, list]:
    """Detect Driving Licence indicators from document text."""
    score = 0
    evidence = []
    upper_text = text.upper()

    dl_labels = [
        r'\bDRIVING\s*LICEN[CS]E\b', r'\bDRIVER\'?S?\s*LICEN[CS]E\b',
        r'\bMOTOR\s*VEHICLE\b', r'\bRTO\b',
        r'\bTRANSPORT\b', r'\bVALIDITY\b',
        r'\bCLASS\s*OF\s*VEHICLE\b', r'\bLMV\b|\bMCWG\b',
        r'\bBLOOD\s*GROUP\b', r'\bISSUING\s*AUTHORITY\b',
        r'\bDL\s*NO\b', r'\bLICEN[CS]E\s*(?:NO|NUMBER)\b',
    ]
    for pattern in dl_labels:
        if re.search(pattern, upper_text):
            score += 2
            evidence.append(f"Label match: {pattern}")

    # DL number pattern (state code + digits, e.g., KA01-2020-1234567)
    dl_nums = re.findall(r'\b[A-Z]{2}\d{2}[\s\-]?\d{4}[\s\-]?\d{7}\b', upper_text)
    if dl_nums:
        score += 4
        evidence.append("Driving licence number pattern found")

    return max(score, 0), evidence


def _detect_educational_cert_indicators(text: str) -> Tuple[int, list]:
    """Detect Educational Certificate indicators from document text."""
    score = 0
    evidence = []
    upper_text = text.upper()

    edu_labels = [
        r'\bCERTIFICATE\b', r'\bDEGREE\b', r'\bDIPLOMA\b',
        r'\bUNIVERSITY\b', r'\bINSTITUT(?:E|ION)\b', r'\bCOLLEGE\b',
        r'\bBACHELOR\b', r'\bMASTER\b', r'\bB\.?TECH\b', r'\bM\.?TECH\b',
        r'\bB\.?SC\b', r'\bM\.?SC\b', r'\bB\.?A\b', r'\bM\.?A\b',
        r'\bPH\.?D\b', r'\bGRADUATI(?:ON|NG)\b',
        r'\bEXAMINATION\b', r'\bRESULT\b',
        r'\bMARKS?\b', r'\bGRADE\b', r'\bCGPA\b', r'\bGPA\b',
        r'\bPASSED\b', r'\bACADEMIC\b', r'\bSEMESTER\b',
        r'\bBOARD\s*OF\b', r'\bREGISTRAR\b', r'\bCONVOCATION\b',
    ]
    for pattern in edu_labels:
        if re.search(pattern, upper_text):
            score += 2
            evidence.append(f"Label match: {pattern}")

    return max(score, 0), evidence


# ---------------------------------------------------------------------------
# Core detection engine
# ---------------------------------------------------------------------------
DETECTOR_MAP = {
    "Aadhaar Card": _detect_aadhaar_indicators,
    "PAN Card": _detect_pan_indicators,
    "Passport": _detect_passport_indicators,
    "Driving Licence": _detect_driving_licence_indicators,
    "Educational Certificate": _detect_educational_cert_indicators,
}


def detect_document_type(text: str) -> Dict[str, Any]:
    """
    Analyse extracted text and return the most likely document type
    along with scores for all categories.

    Returns:
        {
            "detected_type": str or None,
            "confidence": "High" | "Medium" | "Low" | "None",
            "scores": {category: score, ...},
            "evidence": {category: [evidence_strings], ...},
        }
    """
    if not text or not text.strip():
        return {
            "detected_type": None,
            "confidence": "None",
            "scores": {},
            "evidence": {},
        }

    scores = {}
    evidence = {}

    for category, detector_fn in DETECTOR_MAP.items():
        cat_score, cat_evidence = detector_fn(text)
        scores[category] = cat_score
        evidence[category] = cat_evidence

    # Pick category with highest score
    if not scores or max(scores.values()) == 0:
        return {
            "detected_type": None,
            "confidence": "None",
            "scores": scores,
            "evidence": evidence,
        }

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    # Confidence thresholds
    if best_score >= 8:
        confidence = "High"
    elif best_score >= 4:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "detected_type": best_category,
        "confidence": confidence,
        "scores": scores,
        "evidence": evidence,
    }


def detect_document_type_with_ai(text: str) -> Dict[str, Any]:
    """
    Attempt AI-based document type classification via Ollama, then
    combine with rule-based detection.

    Returns same structure as detect_document_type plus:
        "ai_available": bool,
        "ai_detected_type": str or None
    """
    import requests

    # Always get rule-based result first
    rule_result = detect_document_type(text)

    # Attempt AI classification
    try:
        # Check if Ollama is online
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        if resp.status_code != 200:
            rule_result["ai_available"] = False
            rule_result["ai_detected_type"] = None
            return rule_result
    except Exception:
        rule_result["ai_available"] = False
        rule_result["ai_detected_type"] = None
        return rule_result

    prompt = f"""You are a document classification AI. Analyze the following document text and determine the document type.

Reply with ONLY a single JSON object with these exact keys:
- "document_type": one of "Aadhaar Card", "PAN Card", "Passport", "Driving Licence", "Educational Certificate", or "Unknown"
- "confidence": one of "High", "Medium", "Low"
- "reason": a brief one-sentence explanation

DOCUMENT TEXT:
\"\"\"
{text[:3000]}
\"\"\"
"""
    import json
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 256},
        }
        ai_resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=30.0
        )
        if ai_resp.status_code == 200:
            raw = ai_resp.json().get("response", "")
            # Parse JSON from response
            cleaned = raw.strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(cleaned[start : end + 1])
                ai_type = parsed.get("document_type")
                if ai_type and ai_type != "Unknown":
                    rule_result["ai_available"] = True
                    rule_result["ai_detected_type"] = ai_type

                    # Boost score if AI agrees with rule-based top pick
                    if ai_type == rule_result.get("detected_type"):
                        rule_result["confidence"] = "High"
                    elif ai_type in DETECTOR_MAP:
                        # If AI says something different with high confidence,
                        # and rule-based is low confidence, prefer AI
                        ai_conf = parsed.get("confidence", "Low")
                        if rule_result["confidence"] in ("Low", "None") and ai_conf == "High":
                            rule_result["detected_type"] = ai_type
                            rule_result["confidence"] = "Medium"
                    return rule_result

        rule_result["ai_available"] = True
        rule_result["ai_detected_type"] = None
    except Exception:
        rule_result["ai_available"] = False
        rule_result["ai_detected_type"] = None

    return rule_result


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_document_type(
    selected_type: str,
    extracted_text: str,
    use_ai: bool = True,
) -> Dict[str, Any]:
    """
    Validate that an uploaded document matches the selected document category.

    Args:
        selected_type: The category chosen by the user (e.g. "Aadhaar Card").
        extracted_text: The text extracted from the uploaded document.
        use_ai: Whether to attempt AI classification (default True).

    Returns:
        {
            "status": STATUS_MATCHED | STATUS_MISMATCH | STATUS_INCONCLUSIVE | STATUS_AWAITING_REVIEW,
            "selected_type": str,
            "detected_type": str or None,
            "confidence": str,
            "message": str,
            "explanation": str,
            "allow_submission": bool,
            "scores": dict,
            "evidence": dict,
        }
    """
    result_base = {
        "selected_type": selected_type,
        "detected_type": None,
        "confidence": "None",
        "message": "",
        "explanation": "",
        "allow_submission": False,
        "scores": {},
        "evidence": {},
    }

    # If the selected category is a generic type, skip strict validation
    if selected_type in GENERIC_CATEGORIES:
        result_base["status"] = STATUS_MATCHED
        result_base["detected_type"] = selected_type
        result_base["confidence"] = "N/A (Generic Category)"
        result_base["message"] = (
            f"Document accepted under generic category '{selected_type}'. "
            "No strict type validation required."
        )
        result_base["explanation"] = (
            "Generic document categories do not require content-based type matching. "
            "The document will proceed to HR review."
        )
        result_base["allow_submission"] = True
        return result_base

    # Check if text is available
    if not extracted_text or not extracted_text.strip():
        result_base["status"] = STATUS_INCONCLUSIVE
        result_base["message"] = (
            "No readable text could be extracted from the uploaded document. "
            "Please upload a clearer or text-based document."
        )
        result_base["explanation"] = (
            "The document parser returned empty text. This may indicate a "
            "scanned image without OCR, a corrupted file, or an empty document."
        )
        result_base["allow_submission"] = False
        return result_base

    # Run detection
    if use_ai:
        detection = detect_document_type_with_ai(extracted_text)
    else:
        detection = detect_document_type(extracted_text)

    detected_type = detection.get("detected_type")
    confidence = detection.get("confidence", "None")
    scores = detection.get("scores", {})
    evidence = detection.get("evidence", {})

    result_base["detected_type"] = detected_type
    result_base["confidence"] = confidence
    result_base["scores"] = scores
    result_base["evidence"] = evidence

    # No document type detected at all
    if detected_type is None or confidence == "None":
        result_base["status"] = STATUS_INCONCLUSIVE
        result_base["message"] = (
            f"Could not determine the document type. You selected '{selected_type}', "
            "but no sufficient indicators were found in the document content. "
            "Please upload a readable document or use 'Other Supporting Documents'."
        )
        result_base["explanation"] = (
            "The system found no recognizable patterns (headings, numbers, labels) "
            "matching any known document type. The document may be in an "
            "unsupported language, poorly scanned, or not a standard identity/certificate document."
        )
        result_base["allow_submission"] = False
        return result_base

    # Type matches
    if detected_type == selected_type:
        if confidence in ("High", "Medium"):
            result_base["status"] = STATUS_MATCHED
            result_base["message"] = (
                f"Document type validated successfully. The uploaded document "
                f"appears to be a {detected_type} (Confidence: {confidence}). "
                "It will proceed to HR review."
            )
            result_base["explanation"] = (
                f"Multiple indicators confirm this document is consistent with "
                f"a {detected_type}. Found {len(evidence.get(detected_type, []))} "
                f"supporting evidence markers."
            )
            result_base["allow_submission"] = True
        else:
            # Low confidence match
            result_base["status"] = STATUS_AWAITING_REVIEW
            result_base["message"] = (
                f"The uploaded document may be a {detected_type}, but confidence is low. "
                "Submission allowed for HR manual review."
            )
            result_base["explanation"] = (
                "Only a few indicators were found. HR should manually verify "
                "that this document is indeed the correct type before approval."
            )
            result_base["allow_submission"] = True
        return result_base

    # Type mismatch
    result_base["status"] = STATUS_MISMATCH
    result_base["message"] = (
        f"Document type mismatch. You selected '{selected_type}', but the "
        f"uploaded document appears to be a '{detected_type}'. "
        "Please upload the correct document."
    )
    result_base["explanation"] = (
        f"The content analysis detected strong indicators for '{detected_type}' "
        f"(score: {scores.get(detected_type, 0)}) while the selected category "
        f"'{selected_type}' scored only {scores.get(selected_type, 0)}. "
        "This document cannot be submitted under the selected category."
    )
    result_base["allow_submission"] = False
    return result_base
