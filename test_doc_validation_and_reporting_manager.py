"""
Verification tests for:
1. Intelligent Document Type Validation (10 test cases)
2. Reporting Manager Dropdown (6 test cases)
"""

import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import REPORTING_MANAGERS, DOCUMENT_TYPES
from utils.document_type_validator import (
    validate_document_type,
    detect_document_type,
    detect_document_type_with_ai,
    mask_aadhaar,
    mask_pan,
    STATUS_MATCHED,
    STATUS_MISMATCH,
    STATUS_INCONCLUSIVE,
    STATUS_AWAITING_REVIEW
)
from database.db import (
    register_new_employee,
    get_employee_by_id,
    update_employee,
    save_uploaded_document,
    get_document_by_id,
    delete_employee
)

def test_document_validation_cases():
    print("\n--- RUNNING DOCUMENT TYPE VALIDATION TESTS (10 Cases) ---")
    
    # Sample realistic extracted text
    aadhaar_sample_text = """
    GOVERNMENT OF INDIA
    Unique Identification Authority of India
    Enrollment No: 1234/56789/01234
    To:
    Alexander Vance
    DOB: 15/08/1990
    Male
    Address: 123 Innovation Way, Tech Park, Bangalore 560001
    Your Aadhaar No.: 4589 1234 5678
    VID: 9182 7364 5512 3456
    """

    pan_sample_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number Card
    ABCDE1234F
    Name: Alexander Vance
    Father's Name: Robert Vance
    Date of Birth: 15/08/1990
    Signature: A. Vance
    """

    passport_sample_text = """
    PASSPORT
    REPUBLIC OF INDIA
    Type: P   Country Code: IND   Passport No: Z1234567
    Surname: VANCE
    Given Name: ALEXANDER
    Nationality: INDIAN   Sex: M
    Date of Birth: 15/08/1990
    Place of Birth: BANGALORE
    Date of Issue: 10/01/2020   Date of Expiry: 09/01/2030
    P<INDVANCE<<ALEXANDER<<<<<<<<<<<<<<<<<<<<<<
    Z1234567<0IND9008154M3001098<<<<<<<<<<<<<<<04
    """

    uncertain_text = """
    Meeting notes from Tuesday standup.
    Discussed sprint goals and reviewed current backlog.
    Next release is scheduled for end of month.
    """

    # 1. Aadhaar selected + Aadhaar uploaded
    res1 = validate_document_type("Aadhaar Card", aadhaar_sample_text, use_ai=False)
    assert res1["status"] in (STATUS_MATCHED, STATUS_AWAITING_REVIEW), f"Case 1 Failed: {res1}"
    assert res1["detected_type"] == "Aadhaar Card", f"Case 1 Detected wrong type: {res1}"
    assert res1["allow_submission"] is True, f"Case 1 Submission blocked unexpectedly"
    print("  [PASS] Case 1: Aadhaar selected + Aadhaar uploaded -> Matched, Submission Allowed")

    # 2. Aadhaar selected + PAN uploaded
    res2 = validate_document_type("Aadhaar Card", pan_sample_text, use_ai=False)
    assert res2["status"] == STATUS_MISMATCH, f"Case 2 Failed: {res2}"
    assert res2["detected_type"] == "PAN Card", f"Case 2 Wrong detection: {res2}"
    assert res2["allow_submission"] is False, f"Case 2 Submission allowed unexpectedly"
    assert "Document type mismatch" in res2["message"], f"Case 2 Missing mismatch message: {res2['message']}"
    print(f"  [PASS] Case 2: Aadhaar selected + PAN uploaded -> Mismatch Blocked: '{res2['message']}'")

    # 3. PAN selected + Aadhaar uploaded
    res3 = validate_document_type("PAN Card", aadhaar_sample_text, use_ai=False)
    assert res3["status"] == STATUS_MISMATCH, f"Case 3 Failed: {res3}"
    assert res3["detected_type"] == "Aadhaar Card", f"Case 3 Wrong detection: {res3}"
    assert res3["allow_submission"] is False, f"Case 3 Submission allowed unexpectedly"
    print("  [PASS] Case 3: PAN selected + Aadhaar uploaded -> Mismatch Blocked")

    # 4. PAN selected + PAN uploaded
    res4 = validate_document_type("PAN Card", pan_sample_text, use_ai=False)
    assert res4["status"] in (STATUS_MATCHED, STATUS_AWAITING_REVIEW), f"Case 4 Failed: {res4}"
    assert res4["detected_type"] == "PAN Card", f"Case 4 Detected wrong type: {res4}"
    assert res4["allow_submission"] is True, f"Case 4 Submission blocked unexpectedly"
    print("  [PASS] Case 4: PAN selected + PAN uploaded -> Matched, Submission Allowed")

    # 5. Empty document
    res5 = validate_document_type("Aadhaar Card", "", use_ai=False)
    assert res5["status"] == STATUS_INCONCLUSIVE, f"Case 5 Failed: {res5}"
    assert res5["allow_submission"] is False, f"Case 5 Submission allowed for empty document"
    print("  [PASS] Case 5: Empty document -> Inconclusive, Submission Blocked")

    # 6. Corrupted document (no extractable text)
    res6 = validate_document_type("Aadhaar Card", "    \n\t   ", use_ai=False)
    assert res6["status"] == STATUS_INCONCLUSIVE, f"Case 6 Failed: {res6}"
    assert res6["allow_submission"] is False, f"Case 6 Submission allowed for whitespace/corrupt doc"
    print("  [PASS] Case 6: Corrupted document -> Inconclusive, Submission Blocked")

    # 7. Unreadable/scanned document (random non-document content)
    res7 = validate_document_type("Aadhaar Card", "---===### 12345 xyz random noise ===---", use_ai=False)
    assert res7["status"] == STATUS_INCONCLUSIVE, f"Case 7 Failed: {res7}"
    assert res7["allow_submission"] is False, f"Case 7 Submission allowed for unreadable doc"
    print("  [PASS] Case 7: Unreadable/scanned document -> Inconclusive, Submission Blocked")

    # 8. Ollama unavailable (simulated connection failure)
    with patch("requests.get", side_effect=Exception("Connection refused")):
        res8 = validate_document_type("PAN Card", pan_sample_text, use_ai=True)
        assert res8["allow_submission"] is True, f"Case 8 Rule-based fallback should work when Ollama is offline"
        assert res8["detected_type"] == "PAN Card"
        print("  [PASS] Case 8: Ollama unavailable -> Graceful rule-based fallback, accurate matching")

    # 9. Uncertain document classification
    res9 = validate_document_type("Aadhaar Card", uncertain_text, use_ai=False)
    assert res9["status"] == STATUS_INCONCLUSIVE, f"Case 9 Failed: {res9}"
    assert res9["allow_submission"] is False, f"Case 9 Submission allowed for uncertain doc"
    print("  [PASS] Case 9: Uncertain document classification -> Inconclusive, Submission Blocked")

    # 10. Correct document reaches HR review queue
    # Simulate DB storage when validation passes
    # Create temp employee
    reg_payload = {
        "name": "Integration Test Emp",
        "email": f"test_doc_queue_{os.getpid()}@example.com",
        "phone": "+1 555-0199",
        "department": "Engineering",
        "role": "QA Engineer",
        "join_date": "2026-11-01",
        "reporting_manager": "Ananya Rao",
        "work_location": "San Francisco, CA (HQ)",
        "status": "In Progress"
    }
    success, msg, new_emp = register_new_employee(reg_payload)
    assert success, f"Failed to register test emp: {msg}"
    emp_id = new_emp["id"]

    try:
        # Correct document validation check
        val = validate_document_type("Aadhaar Card", aadhaar_sample_text, use_ai=False)
        assert val["allow_submission"] is True

        # Save to DB as would happen in document_processing.py
        doc_id = save_uploaded_document({
            "employee_id": emp_id,
            "document_type": "Aadhaar Card",
            "file_name": "aadhaar_sample.pdf",
            "file_path": "/fake/path/aadhaar.pdf",
            "file_size": 1024,
            "file_type": "PDF",
            "extracted_text": aadhaar_sample_text,
            "extracted_json": "{}",
            "comparison_json": "{}",
            "ai_status": "Processed (Rule-Based Fallback)",
            "verification_status": "Pending HR Review",
            "discrepancy_notes": f"Document type validation: {val['status']} (Confidence: {val['confidence']})."
        })
        saved_doc = get_document_by_id(doc_id)
        assert saved_doc is not None
        assert saved_doc["verification_status"] == "Pending HR Review"
        assert "Aadhaar Card" in saved_doc["document_type"]
        print("  [PASS] Case 10: Validated document safely saved to database in 'Pending HR Review' status")
    finally:
        delete_employee(emp_id)


def test_reporting_manager_cases():
    print("\n--- RUNNING REPORTING MANAGER TESTS (6 Cases) ---")

    expected_managers = [
        "Ananya Rao",
        "Rahul Sharma",
        "Priya Nair",
        "Arjun Kumar",
        "Sneha Reddy"
    ]

    # 1. All five names appear in the centralized list
    assert len(REPORTING_MANAGERS) == 5, f"Expected 5 managers, found {len(REPORTING_MANAGERS)}"
    for mgr in expected_managers:
        assert mgr in REPORTING_MANAGERS, f"Manager {mgr} not found in REPORTING_MANAGERS"
    print("  [PASS] Case 1: All five predefined managers present in config.REPORTING_MANAGERS")

    # 2. Each manager can be selected & registered
    test_emp_ids = []
    try:
        for idx, mgr in enumerate(expected_managers):
            emp_data = {
                "name": f"Manager Test Candidate {idx+1}",
                "email": f"mgr_test_{idx+1}_{os.getpid()}@example.com",
                "phone": f"+1 555-010{idx}",
                "department": "Engineering",
                "role": "Software Engineer",
                "join_date": "2026-11-01",
                "reporting_manager": mgr,
                "work_location": "Remote - US",
                "status": "In Progress"
            }
            ok, msg, created = register_new_employee(emp_data)
            assert ok, f"Failed to register with manager {mgr}: {msg}"
            test_emp_ids.append(created["id"])
            assert created["reporting_manager"] == mgr
        print(f"  [PASS] Case 2: Each of the {len(expected_managers)} managers successfully selected and registered")

        # 3. Selected manager is saved correctly in SQLite
        emp1 = get_employee_by_id(test_emp_ids[0])
        assert emp1["reporting_manager"] == expected_managers[0]
        emp5 = get_employee_by_id(test_emp_ids[4])
        assert emp5["reporting_manager"] == expected_managers[4]
        print("  [PASS] Case 3: Selected manager values verified directly in SQLite persistence layer")

        # 4. Manager appears in employee profile
        profile_emp = get_employee_by_id(test_emp_ids[2])
        assert profile_emp["reporting_manager"] == "Priya Nair"
        print("  [PASS] Case 4: Manager successfully queried and displayed in profile view ('Priya Nair')")

        # 5. Manager remains selected / can be updated when editing an employee
        update_payload = {
            "name": profile_emp["name"],
            "email": profile_emp["email"],
            "phone": profile_emp["phone"],
            "department": profile_emp["department"],
            "role": profile_emp["role"],
            "join_date": profile_emp["join_date"],
            "reporting_manager": "Sneha Reddy",  # Switch manager
            "work_location": profile_emp["work_location"],
            "status": "In Progress"
        }
        ok_up, msg_up = update_employee(test_emp_ids[2], update_payload)
        assert ok_up, f"Failed to update employee manager: {msg_up}"
        updated_emp = get_employee_by_id(test_emp_ids[2])
        assert updated_emp["reporting_manager"] == "Sneha Reddy"
        print("  [PASS] Case 5: Manager update persisted and retrieved on edit ('Priya Nair' -> 'Sneha Reddy')")

        # 6. Existing employee records remain compatible (e.g., custom/legacy manager)
        legacy_data = {
            "name": "Legacy Employee",
            "email": f"legacy_{os.getpid()}@example.com",
            "phone": "+1 555-9999",
            "department": "Operations",
            "role": "Coordinator",
            "join_date": "2025-01-01",
            "reporting_manager": "Custom External Director",
            "work_location": "Other",
            "status": "Completed"
        }
        ok_leg, _, leg_emp = register_new_employee(legacy_data)
        test_emp_ids.append(leg_emp["id"])
        fetched_leg = get_employee_by_id(leg_emp["id"])
        assert fetched_leg["reporting_manager"] == "Custom External Director"
        print("  [PASS] Case 6: Existing/custom legacy manager strings remain fully backwards compatible")

    finally:
        for tid in test_emp_ids:
            try:
                delete_employee(tid)
            except Exception:
                pass


def test_privacy_and_masking():
    print("\n--- RUNNING PRIVACY & SENSITIVE DATA MASKING TESTS ---")
    
    # Aadhaar masking
    m1 = mask_aadhaar("123456789012")
    assert m1 == "XXXX-XXXX-9012", f"Failed Aadhaar mask: {m1}"
    assert "1234" not in m1, "Aadhaar prefix must not be exposed"

    # PAN masking
    m2 = mask_pan("ABCDE1234F")
    assert "ABC" not in m2, "PAN first letters must be masked"
    assert "F" in m2, "PAN format mask check"
    
    print("  [PASS] Aadhaar and PAN masking functions securely conceal sensitive PII identifiers")


if __name__ == "__main__":
    test_document_validation_cases()
    test_reporting_manager_cases()
    test_privacy_and_masking()
    print("\n=======================================================")
    print("ALL 10 DOCUMENT VALIDATION + 6 REPORTING MANAGER TESTS PASSED!")
    print("=======================================================\n")
