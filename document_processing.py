"""
AI Document Processing module for AI-Powered Employee Onboarding System.
Handles document upload (PDF, DOCX, XLSX, XLS), text extraction,
local AI structured extraction (Ollama Gemma 3 1B), comparison with registration,
and human-in-the-loop review.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from config import UPLOADS_DIR, DOCUMENT_TYPES, OLLAMA_MODEL
from database.db import (
    get_all_employees,
    get_employee_by_id,
    save_uploaded_document,
    get_documents_by_employee,
    get_document_by_id,
    update_document_review,
    get_all_documents_with_employee_info
)
from utils.document_parser import extract_document_text
from utils.ai_extractor import (
    check_ollama_status,
    extract_structured_fields,
    compare_extraction_with_registration
)
from utils.document_type_validator import (
    validate_document_type,
    VALIDATED_CATEGORIES,
    STATUS_MATCHED,
    STATUS_MISMATCH,
    STATUS_INCONCLUSIVE,
    STATUS_AWAITING_REVIEW,
)


def format_file_size(size_in_bytes: int) -> str:
    """Formats file size into human-readable string."""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"


def render_document_processing():
    """Renders the AI-Powered Document Processing interface."""

    # 1. Header Banner
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">🤖 AI-Powered Document Processing</h1>
            <p class="header-subtitle">
                Upload new hire PDFs, Word documents, and spreadsheets for automatic text extraction, 
                local AI structured analysis (Ollama Gemma 3 1B), and profile consistency comparison.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Local AI & Policy Banner
    is_ollama_online, ollama_msg, available_models = check_ollama_status()
    model_installed = any(OLLAMA_MODEL in m for m in available_models)

    if is_ollama_online:
        ai_badge = f'<span style="color: #15803d; font-weight: 700;">🟢 Local Ollama Online ({OLLAMA_MODEL})</span>'
    else:
        ai_badge = f'<span style="color: #b45309; font-weight: 700;">🟡 Ollama Offline (Rule-based Fallback Active)</span>'

    st.markdown(f"""
        <div class="info-callout" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem;">
            <div>
                <strong>🛡️ HR Governance & Identity Disclaimer:</strong> AI parsing assists HR by extracting information,
                but <strong>does not verify identity</strong>. All documents and potential discrepancies require 
                <strong>mandatory Human HR Review & Approval</strong>.
            </div>
            <div style="background: #ffffff; padding: 0.4rem 0.8rem; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 0.85rem;">
                {ai_badge}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 3. Main Tabs
    tab_upload, tab_review, tab_roster = st.tabs([
        "📤 Upload & Process Documents",
        "🔍 Document Review & Comparison",
        "📋 Uploaded Documents Roster"
    ])

    # ---------------- TAB 1: UPLOAD & PROCESS ----------------
    with tab_upload:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        employees = get_all_employees()
        if not employees:
            st.warning("No employees registered in the system yet. Please register an employee first.")
            return

        col_emp, col_type = st.columns([3, 2])

        with col_emp:
            emp_options = {
                f"{e['employee_code']} — {e['name']} ({e['department']})": e["id"]
                for e in employees
            }
            selected_emp_label = st.selectbox(
                "Select Candidate / Employee *",
                options=list(emp_options.keys()),
                help="Choose the employee this document belongs to"
            )
            selected_emp_id = emp_options[selected_emp_label]
            selected_emp = get_employee_by_id(selected_emp_id)

        with col_type:
            doc_type = st.selectbox(
                "Document Classification *",
                options=DOCUMENT_TYPES,
                help="Classification category for the uploaded file"
            )

        # File Uploader supporting PDF, DOCX, XLSX, XLS
        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Upload Candidate Documents (Supports PDF, DOCX, XLSX, XLS)",
            type=["pdf", "docx", "xlsx", "xls"],
            accept_multiple_files=True,
            help="Upload one or multiple documents for this candidate (Max 15MB each)"
        )

        # Process Button
        if uploaded_files:
            st.markdown(f"""
                <div style="font-size: 0.88rem; color: #475569; margin-bottom: 0.8rem;">
                    📁 <strong>{len(uploaded_files)}</strong> file(s) selected for <strong>{selected_emp['name']}</strong> ({selected_emp['employee_code']}).
                </div>
            """, unsafe_allow_html=True)

            if st.button("⚡ Process & Analyze Documents with AI", type="primary", use_container_width=True):
                progress_bar = st.progress(0.0)
                status_placeholder = st.empty()

                processed_results = []

                for idx, uploaded_file in enumerate(uploaded_files):
                    status_placeholder.info(f"Processing ({idx + 1}/{len(uploaded_files)}): {uploaded_file.name}...")

                    # 1. Validate file size (15MB limit)
                    file_bytes = uploaded_file.read()
                    file_size = len(file_bytes)
                    
                    if file_size > 15 * 1024 * 1024:
                        st.error(f"❌ File '{uploaded_file.name}' exceeds the 15MB size limit ({format_file_size(file_size)}). Skipped.")
                        continue

                    # 2. Save securely to data/uploads with guaranteed collision prevention
                    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', uploaded_file.name)
                    ts = int(datetime.now().timestamp())
                    unique_filename = f"{selected_emp['employee_code']}_{ts}_{clean_name}"
                    save_path = os.path.join(UPLOADS_DIR, unique_filename)
                    counter = 1
                    while os.path.exists(save_path):
                        unique_filename = f"{selected_emp['employee_code']}_{ts}_{counter}_{clean_name}"
                        save_path = os.path.join(UPLOADS_DIR, unique_filename)
                        counter += 1

                    with open(save_path, "wb") as f:
                        f.write(file_bytes)

                    # 3. Extract readable text using specialized parsers
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    success_extract, raw_text, extract_msg = extract_document_text(save_path)

                    if not success_extract:
                        if doc_type in VALIDATED_CATEGORIES:
                            type_validation = validate_document_type(
                                selected_type=doc_type,
                                extracted_text="",
                                use_ai=False,
                            )
                            type_validation["explanation"] = f"Extraction failed: {extract_msg}. The document appears to be corrupted, empty, or an unreadable scanned file."
                            
                            val_status = type_validation["status"]
                            val_msg = type_validation["message"]
                            val_explain = type_validation["explanation"]
                            detected = type_validation.get("detected_type") or "Unknown"

                            st.markdown(f"""
                                <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-left: 5px solid #92400E; border-radius: 10px; padding: 1.2rem; margin-top: 0.8rem; margin-bottom: 0.8rem;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 0.6rem;">
                                        <div style="font-size: 1.05rem; font-weight: 700; color: #92400E;">
                                            🟡 Document Type Validation: {val_status}
                                        </div>
                                        <span style="background: #ffffff; padding: 0.25rem 0.7rem; border-radius: 6px; font-size: 0.82rem; font-weight: 600; color: #475569; border: 1px solid #CBD5E1;">
                                            {uploaded_file.name}
                                        </span>
                                    </div>
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; font-size: 0.9rem; margin-bottom: 0.8rem;">
                                        <div><strong>Selected Type:</strong> {doc_type}</div>
                                        <div><strong>Detected Type:</strong> {detected}</div>
                                        <div><strong>Confidence:</strong> None</div>
                                        <div><strong>Submission:</strong> <span style="color: #92400E; font-weight: 700;">Blocked</span></div>
                                    </div>
                                    <div style="font-size: 0.88rem; color: #92400E; margin-bottom: 0.5rem;">
                                        <strong>Reason:</strong> {val_msg}
                                    </div>
                                    <div style="font-size: 0.82rem; color: #64748B; background: #ffffff; padding: 0.6rem 0.8rem; border-radius: 6px; border: 1px solid #E2E8F0;">
                                        <strong>Details:</strong> {val_explain}
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)

                            try:
                                os.remove(save_path)
                            except OSError:
                                pass
                            progress_bar.progress((idx + 1) / len(uploaded_files))
                            continue
                        else:
                            st.error(f"❌ Text extraction failed for '{uploaded_file.name}': {extract_msg}")
                            # Save with failure status for generic category
                            save_uploaded_document({
                                "employee_id": selected_emp_id,
                                "document_type": doc_type,
                                "file_name": uploaded_file.name,
                                "file_path": save_path,
                                "file_size": file_size,
                                "file_type": ext.upper().replace(".", ""),
                                "extracted_text": "",
                                "extracted_json": json.dumps({}),
                                "comparison_json": json.dumps({}),
                                "ai_status": "Extraction Failed",
                                "verification_status": "Flagged for Revision",
                                "discrepancy_notes": f"Parser error: {extract_msg}"
                            })
                            continue

                    # 3b. Document Type Validation (for validated categories)
                    type_validation = validate_document_type(
                        selected_type=doc_type,
                        extracted_text=raw_text,
                        use_ai=True,
                    )

                    if not type_validation["allow_submission"]:
                        # Block submission — display validation result and skip
                        val_status = type_validation["status"]
                        val_msg = type_validation["message"]
                        val_explain = type_validation["explanation"]
                        detected = type_validation.get("detected_type") or "Unknown"

                        if val_status == STATUS_MISMATCH:
                            badge_bg = "#FEF2F2"; badge_border = "#FECACA"; badge_color = "#991B1B"; badge_icon = "🔴"
                        else:
                            badge_bg = "#FFFBEB"; badge_border = "#FDE68A"; badge_color = "#92400E"; badge_icon = "🟡"

                        st.markdown(f"""
                            <div style="background: {badge_bg}; border: 1px solid {badge_border}; border-left: 5px solid {badge_color}; border-radius: 10px; padding: 1.2rem; margin-top: 0.8rem; margin-bottom: 0.8rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 0.6rem;">
                                    <div style="font-size: 1.05rem; font-weight: 700; color: {badge_color};">
                                        {badge_icon} Document Type Validation: {val_status}
                                    </div>
                                    <span style="background: #ffffff; padding: 0.25rem 0.7rem; border-radius: 6px; font-size: 0.82rem; font-weight: 600; color: #475569; border: 1px solid #CBD5E1;">
                                        {uploaded_file.name}
                                    </span>
                                </div>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; font-size: 0.9rem; margin-bottom: 0.8rem;">
                                    <div><strong>Selected Type:</strong> {doc_type}</div>
                                    <div><strong>Detected Type:</strong> {detected}</div>
                                    <div><strong>Confidence:</strong> {type_validation.get('confidence', 'N/A')}</div>
                                    <div><strong>Submission:</strong> <span style="color: {badge_color}; font-weight: 700;">Blocked</span></div>
                                </div>
                                <div style="font-size: 0.88rem; color: {badge_color}; margin-bottom: 0.5rem;">
                                    <strong>Reason:</strong> {val_msg}
                                </div>
                                <div style="font-size: 0.82rem; color: #64748B; background: #ffffff; padding: 0.6rem 0.8rem; border-radius: 6px; border: 1px solid #E2E8F0;">
                                    <strong>Details:</strong> {val_explain}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        # Clean up saved file since submission is blocked
                        try:
                            os.remove(save_path)
                        except OSError:
                            pass
                        progress_bar.progress((idx + 1) / len(uploaded_files))
                        continue

                    # 4. Extract structured fields via Ollama / Fallback
                    is_ai, structured_data, ai_msg = extract_structured_fields(raw_text)

                    # 5. Compare with employee registration
                    comparison = compare_extraction_with_registration(structured_data, selected_emp)

                    # 6. Determine verification status and discrepancy notes
                    mismatches = comparison["counts"]["mismatches"]
                    if mismatches > 0:
                        discrepancy_summary = f"{mismatches} discrepancy/mismatch detected against registered profile."
                    else:
                        discrepancy_summary = "Fields align with registration. Pending HR review."

                    # Include type validation info in discrepancy notes
                    type_note = f"Document type validation: {type_validation['status']} (Confidence: {type_validation['confidence']})."
                    if type_validation["status"] == STATUS_AWAITING_REVIEW:
                        type_note += " Low-confidence match — HR should verify document type manually."
                    discrepancy_summary = f"{type_note} {discrepancy_summary}"

                    # 7. Save to SQLite database
                    doc_id = save_uploaded_document({
                        "employee_id": selected_emp_id,
                        "document_type": doc_type,
                        "file_name": uploaded_file.name,
                        "file_path": save_path,
                        "file_size": file_size,
                        "file_type": ext.upper().replace(".", ""),
                        "extracted_text": raw_text,
                        "extracted_json": json.dumps(structured_data),
                        "comparison_json": json.dumps(comparison),
                        "ai_status": "Processed (Ollama)" if is_ai else "Processed (Rule-Based Fallback)",
                        "verification_status": "Pending HR Review",
                        "discrepancy_notes": discrepancy_summary
                    })

                    processed_results.append({
                        "doc_id": doc_id,
                        "filename": uploaded_file.name,
                        "size": format_file_size(file_size),
                        "ai_status": "Ollama Gemma 3 1B" if is_ai else "Rule-based Fallback",
                        "comparison": comparison,
                        "raw_text": raw_text,
                        "structured_data": structured_data,
                        "type_validation": type_validation,
                    })

                    progress_bar.progress((idx + 1) / len(uploaded_files))

                status_placeholder.success(f"🎉 Successfully processed {len(processed_results)} document(s) for {selected_emp['name']}!")

                # Display Results Summary
                for res in processed_results:
                    comp = res["comparison"]
                    counts = comp["counts"]
                    tv = res.get("type_validation", {})
                    tv_status = tv.get("status", "N/A")
                    tv_detected = tv.get("detected_type") or "N/A"
                    tv_confidence = tv.get("confidence", "N/A")

                    # Type validation badge color
                    if tv_status == STATUS_MATCHED:
                        tv_badge_bg = "#DCFCE7"; tv_badge_color = "#166534"
                    elif tv_status == STATUS_AWAITING_REVIEW:
                        tv_badge_bg = "#FEF3C7"; tv_badge_color = "#92400E"
                    else:
                        tv_badge_bg = "#EFF6FF"; tv_badge_color = "#1E40AF"
                    
                    st.markdown(f"""
                        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.2rem; margin-top: 1rem; margin-bottom: 1rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 0.6rem; margin-bottom: 0.8rem;">
                                <div>
                                    <strong style="font-size: 1.05rem; color: #0f172a;">📄 {res['filename']}</strong>
                                    <span style="font-size: 0.82rem; color: #64748b; margin-left: 0.5rem;">({res['size']})</span>
                                </div>
                                <span style="background: #eff6ff; color: #1e40af; font-weight: 600; font-size: 0.8rem; padding: 0.2rem 0.6rem; border-radius: 6px;">
                                    {res['ai_status']}
                                </span>
                            </div>
                            <div style="display: flex; gap: 0.8rem; font-size: 0.85rem; margin-bottom: 0.8rem; flex-wrap: wrap; align-items: center;">
                                <span style="background: {tv_badge_bg}; color: {tv_badge_color}; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem;">
                                    📋 Type: {tv_status}
                                </span>
                                <span style="color: #64748B; font-size: 0.82rem;">
                                    Detected: <strong>{tv_detected}</strong> • Confidence: <strong>{tv_confidence}</strong>
                                </span>
                            </div>
                            <div style="display: flex; gap: 1rem; font-size: 0.88rem; margin-bottom: 0.8rem; flex-wrap: wrap;">
                                <span style="color: #10B981; font-weight: 600;">🟢 {counts['matches']} Matched</span>
                                <span style="color: #EF4444; font-weight: 600;">🔴 {counts['mismatches']} Mismatches</span>
                                <span style="color: #F59E0B; font-weight: 600;">🟡 {counts['missing']} Missing in Doc</span>
                                <span style="color: #4F46E5; font-weight: 600;">ℹ️ {counts['manual_review']} Manual Verifications</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    with st.expander(f"🔍 View Comparison Details & Raw Text for {res['filename']}"):
                        comp_df = pd.DataFrame([
                            {
                                "Field": v["label"],
                                "Registered in Profile": v["registered"],
                                "Extracted from Document": v["extracted"],
                                "Result": v["badge"],
                                "Audit Notes": v["notes"]
                            }
                            for k, v in comp["fields"].items()
                        ])
                        st.dataframe(comp_df, use_container_width=True, hide_index=True)

                        st.markdown("**Raw Extracted Document Text Preview:**")
                        st.text_area(
                            f"raw_text_{res['doc_id']}",
                            value=res["raw_text"][:2000],
                            height=150,
                            disabled=True,
                            label_visibility="collapsed"
                        )

    # ---------------- TAB 2: DOCUMENT REVIEW & COMPARISON ----------------
    with tab_review:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 🔍 Human HR Document Review & Discrepancy Correction")
        st.markdown("<p style='font-size: 0.88rem; color: #64748b;'>Review AI extraction findings, verify against registration profile, correct fields, and approve or flag documents.</p>", unsafe_allow_html=True)

        all_docs = get_all_documents_with_employee_info(limit=50)

        if not all_docs:
            st.info("No documents have been uploaded yet. Upload candidate documents in the 'Upload & Process' tab.")
            return

        doc_selector_options = {
            f"Doc #{d['id']}: {d['file_name']} — {d['employee_name']} ({d['employee_code']}) [{d['verification_status']}]": d["id"]
            for d in all_docs
        }

        selected_doc_key = st.selectbox(
            "Select Document to Inspect & Review:",
            options=list(doc_selector_options.keys())
        )

        selected_doc_id = doc_selector_options[selected_doc_key]
        doc = get_document_by_id(selected_doc_id)

        if not doc:
            st.error("Could not load document record.")
            return

        # Parse extracted JSON and comparison JSON safely
        try:
            extracted_json = json.loads(doc.get("extracted_json") or "{}")
        except Exception:
            extracted_json = {}

        try:
            comparison_json = json.loads(doc.get("comparison_json") or "{}")
        except Exception:
            comparison_json = {}

        # Document Overview Header
        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; margin-top: 1rem; margin-bottom: 1.2rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <span style="font-size: 0.8rem; font-weight: 700; color: #4F46E5; background: #EEF2FF; padding: 0.2rem 0.6rem; border-radius: 4px; border: 1px solid #C7D2FE;">
                            {doc['document_type']}
                        </span>
                        <h3 style="margin: 0.3rem 0 0.1rem 0; font-size: 1.3rem; color: #0F172A;">{doc['file_name']}</h3>
                        <span style="font-size: 0.88rem; color: #64748B;">
                            Candidate: <strong>{doc['employee_name']}</strong> ({doc['employee_code']}) • {doc['department']}
                        </span>
                    </div>
                    <div style="text-align: right;">
                        <span style="display: inline-block; padding: 0.35rem 0.8rem; border-radius: 9999px; font-weight: 700; font-size: 0.85rem; background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;">
                            Status: {doc['verification_status']}
                        </span>
                        <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.3rem;">
                            Uploaded: {str(doc['created_at'])[:19]}
                        </div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Comparison Grid
        if "fields" in comparison_json:
            st.markdown("###### 📊 Registration vs Document Comparison")
            comp_display = []
            for f_key, f_data in comparison_json["fields"].items():
                comp_display.append({
                    "Field": f_data["label"],
                    "Registered Value": f_data["registered"],
                    "Extracted from Document": f_data["extracted"],
                    "Status": f_data["badge"],
                    "Notes": f_data["notes"]
                })
            st.dataframe(pd.DataFrame(comp_display), use_container_width=True, hide_index=True)

        # Raw text expander
        with st.expander("📄 View Full Extracted Document Text"):
            st.text_area(
                "raw_text_review",
                value=doc.get("extracted_text") or "No text content.",
                height=180,
                disabled=True,
                label_visibility="collapsed"
            )

        # Editable Review Form
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("##### ✏️ Correct Extracted Fields & Confirm HR Review")

        with st.form(f"hr_review_form_{doc['id']}"):
            col_rev1, col_rev2 = st.columns(2)

            with col_rev1:
                rev_name = st.text_input("Full Name", value=str(extracted_json.get("full_name") or ""))
                rev_email = st.text_input("Email Address", value=str(extracted_json.get("email") or ""))
                rev_phone = st.text_input("Phone Number", value=str(extracted_json.get("phone") or ""))
                rev_dept = st.text_input("Department", value=str(extracted_json.get("department") or ""))

            with col_rev2:
                rev_role = st.text_input("Job Role", value=str(extracted_json.get("job_role") or ""))
                rev_date = st.text_input("Joining Date (YYYY-MM-DD)", value=str(extracted_json.get("joining_date") or ""))
                rev_edu = st.text_input("Education / Credentials", value=str(extracted_json.get("education") or ""))
                skills_raw = extracted_json.get("skills") or []
                skills_val = ", ".join(skills_raw) if isinstance(skills_raw, list) else str(skills_raw)
                rev_skills = st.text_input("Skills (comma-separated)", value=skills_val)

            discrepancy_notes = st.text_area(
                "HR Discrepancy & Verification Notes",
                value=doc.get("discrepancy_notes") or "",
                placeholder="Enter notes on discrepancies, verified signatures, or reason for rejection/approval..."
            )

            status_options = ["Pending HR Review", "Approved", "Flagged for Revision"]
            cur_doc_status = doc.get("verification_status", "Pending HR Review")
            status_idx = status_options.index(cur_doc_status) if cur_doc_status in status_options else 0
            new_verification_status = st.selectbox(
                "HR Verification Decision *",
                options=status_options,
                index=status_idx,
                help="Note: AI extraction does not automatically approve compliance."
            )

            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            submit_review = st.form_submit_button("💾 Save Verified Extraction & HR Decision", type="primary", use_container_width=True)

        if submit_review:
            # Reconstruct clean JSON
            skills_list = [s.strip() for s in rev_skills.split(",") if s.strip()] if rev_skills else []
            updated_fields = {
                "full_name": rev_name.strip() or None,
                "email": rev_email.strip() or None,
                "phone": rev_phone.strip() or None,
                "department": rev_dept.strip() or None,
                "job_role": rev_role.strip() or None,
                "joining_date": rev_date.strip() or None,
                "education": rev_edu.strip() or None,
                "skills": skills_list
            }

            ok, msg = update_document_review(
                document_id=doc["id"],
                extracted_json=json.dumps(updated_fields),
                discrepancy_notes=discrepancy_notes.strip(),
                verification_status=new_verification_status,
                reviewed_by="HR Operations Specialist"
            )

            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ Error: {msg}")

    # ---------------- TAB 3: DOCUMENT ROSTER ----------------
    with tab_roster:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📋 Complete Document Verification Roster")
        st.markdown("<p style='font-size: 0.88rem; color: #64748b;'>All uploaded documents, their AI processing engines, and HR review statuses.</p>", unsafe_allow_html=True)

        docs_all = get_all_documents_with_employee_info(limit=100)
        if docs_all:
            df_docs = pd.DataFrame([
                {
                    "ID": f"#{d['id']}",
                    "Candidate Name": d["employee_name"],
                    "Emp Code": d["employee_code"],
                    "Document Type": d["document_type"],
                    "File Name": d["file_name"],
                    "Format": d.get("file_type") or "DOC",
                    "AI Status": d.get("ai_status") or "Pending",
                    "HR Verification": d["verification_status"],
                    "Uploaded": str(d["created_at"])[:16]
                }
                for d in docs_all
            ])
            st.dataframe(df_docs, use_container_width=True, hide_index=True)
        else:
            st.info("No documents found in repository.")
