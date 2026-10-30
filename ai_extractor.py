"""
Local AI Extraction module integrating with Ollama (Gemma 3 1B)
and providing robust rule-based fallback, JSON parsing, and registration comparison.
"""

import json
import re
from typing import Dict, Any, Tuple, List, Optional
import requests
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


def check_ollama_status() -> Tuple[bool, str, List[str]]:
    """
    Checks if local Ollama daemon is running and lists installed models.
    
    Returns:
        (is_running: bool, status_message: str, models: list)
    """
    url = f"{OLLAMA_BASE_URL}/api/tags"
    try:
        response = requests.get(url, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return True, "Ollama service is online", models
        return False, f"Ollama returned HTTP status {response.status_code}", []
    except requests.exceptions.ConnectTimeout:
        return False, f"Connection to Ollama timed out at {OLLAMA_BASE_URL}", []
    except requests.exceptions.ConnectionError:
        return False, f"Ollama is offline or unreachable at {OLLAMA_BASE_URL}", []
    except Exception as e:
        return False, f"Ollama status check failed: {str(e)}", []


def clean_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Strips markdown code fences and parses JSON safely."""
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()
    
    # Strip markdown code blocks (e.g. ```json ... ```)
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Find first '{' and last '}'
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx + 1]

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


def rule_based_fallback_extraction(text: str) -> Dict[str, Any]:
    """
    Extracts basic fields using regex and heuristic patterns when
    Ollama is offline or unable to parse JSON.
    Never uses fake AI responses.
    """
    data: Dict[str, Any] = {
        "full_name": None,
        "email": None,
        "phone": None,
        "department": None,
        "job_role": None,
        "joining_date": None,
        "education": None,
        "skills": []
    }

    if not text:
        return data

    # 1. Email extraction
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    if email_match:
        data["email"] = email_match.group(0).strip()

    # 2. Phone extraction
    phone_match = re.search(r"(?:Phone[:\s]*)?(\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}", text, re.IGNORECASE)
    if phone_match:
        # Extract phone string without the "Phone:" prefix
        matched_str = phone_match.group(0).strip()
        cleaned_phone = re.sub(r"^(?:Phone[:\s]*)", "", matched_str, flags=re.IGNORECASE).strip()
        data["phone"] = cleaned_phone

    # 3. Date extraction (YYYY-MM-DD or standard formats)
    date_match = re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b", text)
    if date_match:
        data["joining_date"] = date_match.group(0).replace("/", "-")

    # 4. Education heuristics
    edu_keywords = ["Bachelor", "Master", "B.S.", "M.S.", "B.Tech", "Ph.D", "Degree", "University", "College"]
    edu_matches = [kw for kw in edu_keywords if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE)]
    if edu_matches:
        data["education"] = f"Detected references: {', '.join(set(edu_matches))}"

    # 5. Skills heuristics
    tech_keywords = [
        "Python", "SQL", "JavaScript", "TypeScript", "React", "Docker", "AWS",
        "Kubernetes", "Linux", "Git", "Figma", "Machine Learning", "Data Analysis",
        "Java", "C++", "Go", "Pandas", "Streamlit", "API"
    ]
    detected_skills = [
        skill for skill in tech_keywords
        if re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE)
    ]
    if detected_skills:
        data["skills"] = detected_skills

    # 6. Name heuristic (inspect top 3 non-empty lines)
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("---")]
    for line in lines[:3]:
        # If line has 2-4 capitalized words and no email or phone symbols
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w.isalpha()):
            if "@" not in line and not any(char.isdigit() for char in line):
                data["full_name"] = line
                break

    return data


def extract_structured_fields(text: str, model: str = OLLAMA_MODEL) -> Tuple[bool, Dict[str, Any], str]:
    """
    Extracts structured fields from document text using local Ollama (Gemma 3 1B).
    Falls back gracefully to rule-based regex extraction if Ollama is unreachable.
    
    Returns:
        (is_ai_powered: bool, extracted_data: dict, status_message: str)
    """
    if not text or not text.strip():
        empty_data = {
            "full_name": None, "email": None, "phone": None,
            "department": None, "job_role": None, "joining_date": None,
            "education": None, "skills": []
        }
        return False, empty_data, "Document is empty. No text to analyze."

    # Check Ollama health
    is_online, status_msg, models = check_ollama_status()

    if not is_online:
        # Graceful fallback to rule-based extraction
        fallback_data = rule_based_fallback_extraction(text)
        return False, fallback_data, f"Local Ollama unreachable ({status_msg}). Rule-based parser applied."

    # Prepare prompt for Ollama Gemma 3 1B
    prompt = f"""You are an expert HR Document Processing AI.
Extract structured employee onboarding information from the following document text.
Output MUST be a single valid JSON object with the following exact keys:
- "full_name": string or null
- "email": string or null
- "phone": string or null
- "department": string or null
- "job_role": string or null
- "joining_date": string in YYYY-MM-DD format or null
- "education": string describing degree/university or null
- "skills": array of strings (e.g. ["Python", "Docker"]) or []

Do not invent details. If a field is not mentioned in the text, use null.
Do NOT output any markdown commentary outside the JSON object.

DOCUMENT TEXT:
\"\"\"
{text[:4000]}
\"\"\"
"""

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 512
        }
    }

    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=45.0)
        if response.status_code == 200:
            result_json = response.json()
            raw_response = result_json.get("response", "")
            parsed_data = clean_json_response(raw_response)
            
            if parsed_data:
                # Ensure all 8 required keys exist
                standardized = {
                    "full_name": parsed_data.get("full_name"),
                    "email": parsed_data.get("email"),
                    "phone": parsed_data.get("phone"),
                    "department": parsed_data.get("department"),
                    "job_role": parsed_data.get("job_role"),
                    "joining_date": parsed_data.get("joining_date"),
                    "education": parsed_data.get("education"),
                    "skills": parsed_data.get("skills", [])
                }
                return True, standardized, f"Successfully extracted via local Ollama ({model})."
            else:
                # Malformed JSON returned from model
                fallback_data = rule_based_fallback_extraction(text)
                return False, fallback_data, "Ollama returned malformed JSON. Rule-based parser applied as fallback."
        else:
            fallback_data = rule_based_fallback_extraction(text)
            return False, fallback_data, f"Ollama returned HTTP error {response.status_code}. Rule-based parser applied."
            
    except requests.exceptions.Timeout:
        fallback_data = rule_based_fallback_extraction(text)
        return False, fallback_data, "Ollama request timed out after 45s. Rule-based parser applied as fallback."
    except Exception as e:
        fallback_data = rule_based_fallback_extraction(text)
        return False, fallback_data, f"Ollama extraction failed: {str(e)}. Rule-based parser applied."


def normalize_string(val: Any) -> str:
    """Helper to normalize strings for comparison."""
    if val is None:
        return ""
    return str(val).strip().lower()


def normalize_phone(val: Any) -> str:
    """Helper to normalize phone numbers by stripping formatting characters."""
    if val is None:
        return ""
    return re.sub(r"[^0-9]", "", str(val))


def compare_extraction_with_registration(extracted: Dict[str, Any], employee: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compares AI/rule extracted fields against employee registration records.
    
    Fields compared:
        - Full Name
        - Email
        - Phone
        - Department
        - Job Role
        - Joining Date
        - Education (requires manual verification)
        - Skills (requires manual verification)
        
    Classification:
        - MATCH: Extracted value matches registered value.
        - MISMATCH: Extracted value is present and differs from registration.
        - MISSING: Field was not detected in the document.
        - MANUAL_REVIEW: Requires human HR verification.
    """
    comparison: Dict[str, Dict[str, Any]] = {}
    counts = {"matches": 0, "mismatches": 0, "missing": 0, "manual_review": 0}

    # Helper function to classify comparable scalar fields
    def evaluate_field(field_key: str, label: str, ext_val: Any, reg_val: Any, is_phone: bool = False):
        ext_clean = normalize_phone(ext_val) if is_phone else normalize_string(ext_val)
        reg_clean = normalize_phone(reg_val) if is_phone else normalize_string(reg_val)

        if not ext_val or not str(ext_val).strip() or ext_val is None:
            status = "MISSING"
            badge = "🟡 Missing in Document"
            counts["missing"] += 1
            notes = "Field not detected in document."
        elif ext_clean == reg_clean:
            status = "MATCH"
            badge = "🟢 Matching"
            counts["matches"] += 1
            notes = "Values match registered profile."
        else:
            status = "MISMATCH"
            badge = "🔴 Discrepancy"
            counts["mismatches"] += 1
            notes = f"Document states '{ext_val}', but registered profile has '{reg_val}'."

        comparison[field_key] = {
            "label": label,
            "extracted": ext_val,
            "registered": reg_val,
            "status": status,
            "badge": badge,
            "notes": notes
        }

    # Evaluate 6 core fields
    evaluate_field("full_name", "Full Name", extracted.get("full_name"), employee.get("name"))
    evaluate_field("email", "Work Email", extracted.get("email"), employee.get("email"))
    evaluate_field("phone", "Phone Number", extracted.get("phone"), employee.get("phone"), is_phone=True)
    evaluate_field("department", "Department", extracted.get("department"), employee.get("department"))
    evaluate_field("job_role", "Job Role", extracted.get("job_role"), employee.get("role"))
    evaluate_field("joining_date", "Joining Date", extracted.get("joining_date"), employee.get("join_date"))

    # Education (requires manual verification)
    edu_val = extracted.get("education")
    if not edu_val:
        comparison["education"] = {
            "label": "Education / Degree",
            "extracted": "Not Detected",
            "registered": "N/A (Not tracked in registration)",
            "status": "MISSING",
            "badge": "🟡 Not Found",
            "notes": "No educational credentials found in document."
        }
        counts["missing"] += 1
    else:
        comparison["education"] = {
            "label": "Education / Degree",
            "extracted": edu_val,
            "registered": "Requires Verification",
            "status": "MANUAL_REVIEW",
            "badge": "ℹ️ Manual Review Needed",
            "notes": "HR review required to verify credential authenticity."
        }
        counts["manual_review"] += 1

    # Skills (requires manual verification)
    skills_val = extracted.get("skills")
    if not skills_val or (isinstance(skills_val, list) and len(skills_val) == 0):
        comparison["skills"] = {
            "label": "Technical Skills",
            "extracted": "None Detected",
            "registered": "N/A",
            "status": "MISSING",
            "badge": "🟡 Not Found",
            "notes": "No specific skills parsed."
        }
        counts["missing"] += 1
    else:
        skills_str = ", ".join(skills_val) if isinstance(skills_val, list) else str(skills_val)
        comparison["skills"] = {
            "label": "Technical Skills",
            "extracted": skills_str,
            "registered": "Role Profile Alignment",
            "status": "MANUAL_REVIEW",
            "badge": "ℹ️ Manual Review Needed",
            "notes": "Review skills against department role requirements."
        }
        counts["manual_review"] += 1

    # Overall compliance classification
    if counts["mismatches"] > 0:
        overall_status = "Discrepancies Flagged"
    elif counts["matches"] >= 4:
        overall_status = "High Confidence Match"
    else:
        overall_status = "Partial Match (Pending Review)"

    return {
        "fields": comparison,
        "counts": counts,
        "overall_status": overall_status
    }
