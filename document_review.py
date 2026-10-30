"""
Centralized Document Review & Human HR Approval Queue module for OnboardAI.
Provides cross-workforce review queues, document inspection, profile comparison,
explicit approval/rejection/correction workflows, and audit logging.
"""

import os
import json
import streamlit as st
import pandas as pd
from config import DOCUMENT_TYPES
from database.db import (
    get_document_review_metrics,
    get_review_queue_documents,
    get_document_by_id,
    submit_hr_document_decision,
    get_document_audit_trail,
    get_all_audit_logs
)
from utils.ai_extractor import compare_extraction_with_registration


def format_file_size(size_in_bytes: int) -> str:
    """Formats file size into human-readable string."""
    if not size_in_bytes or size_in_bytes <= 0:
        return "N/A"
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"


def render_document_review():
    """Renders the Centralized Document Review & Human HR Approval Queue."""

    # 1. Header Banner
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">🔍 Centralized Document Review & Approval Queue</h1>
            <p class="header-subtitle">
                Centralized human-in-the-loop compliance gateway. Inspect AI-extracted document metadata,
                verify against employee registration profiles, record binding approval decisions, and maintain audit trails.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Key Guardrail Policy Banner
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ Human Verification Mandate:</strong> Local AI (Gemma 3 1B) extracts and compares document fields
            to assist review, but <strong>does not verify identity or grant compliance approval</strong>.
            All documents require explicit, human-controlled review. Rejections and correction requests require documented audit notes.
        </div>
    """, unsafe_allow_html=True)

    # 3. Queue Metric Headline Cards
    metrics = get_document_review_metrics()

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.markdown(f"""
            <div class="stat-card amber">
                <div class="stat-title">Pending HR Review</div>
                <div class="stat-value">{metrics['pending']}</div>
                <div class="stat-subtext">⏳ Awaiting human verification</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col2:
        st.markdown(f"""
            <div class="stat-card emerald">
                <div class="stat-title">Approved</div>
                <div class="stat-value">{metrics['approved']}</div>
                <div class="stat-subtext">✅ Verified and accepted</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col3:
        st.markdown(f"""
            <div class="stat-card rose">
                <div class="stat-title">Rejected</div>
                <div class="stat-value">{metrics['rejected']}</div>
                <div class="stat-subtext">❌ Failed compliance check</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col4:
        st.markdown(f"""
            <div class="stat-card blue">
                <div class="stat-title">Correction Needed</div>
                <div class="stat-value">{metrics['correction_requested']}</div>
                <div class="stat-subtext">🔄 Returned for candidate update</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # 4. Search and Filtering Controls
    st.markdown('<h3 class="section-title">📋 Document Verification Queue</h3>', unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])

    with filter_col1:
        search_query = st.text_input(
            "Search Queue",
            placeholder="Search by candidate name, employee ID (e.g. EMP-1001), or filename...",
            label_visibility="collapsed"
        )

    with filter_col2:
        doc_type_filter = st.selectbox(
            "Document Type Filter",
            options=["All Document Types"] + DOCUMENT_TYPES,
            label_visibility="collapsed"
        )

    with filter_col3:
        status_options = [
            "All Statuses",
            "Pending HR Review",
            "Approved",
            "Rejected",
            "Correction Requested"
        ]
        status_filter = st.selectbox(
            "Review Status Filter",
            options=status_options,
            index=0,
            label_visibility="collapsed"
        )

    # 5. Fetch Queue Items
    queue_docs = get_review_queue_documents(
        search_term=search_query,
        document_type=doc_type_filter,
        review_status=status_filter
    )

    st.markdown(f"""
        <div style="font-size: 0.88rem; color: #64748b; margin-top: -0.3rem; margin-bottom: 1rem;">
            Showing <strong>{len(queue_docs)}</strong> document{'s' if len(queue_docs) != 1 else ''} in verification queue.
        </div>
    """, unsafe_allow_html=True)

    if queue_docs:
        # Queue Table Display
        queue_table_data = []
        for d in queue_docs:
            queue_table_data.append({
                "Doc ID": f"#{d['id']}",
                "Candidate Name": d["employee_name"],
                "Employee ID": d["employee_code"],
                "Document Type": d["document_type"],
                "Filename": d["file_name"],
                "Format": d.get("file_type") or "DOC",
                "AI Extraction": d.get("ai_status") or "Completed",
                "Review Status": d["verification_status"],
                "Uploaded Date": str(d["created_at"])[:16]
            })

        st.dataframe(
            pd.DataFrame(queue_table_data),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No documents match the specified search and filter criteria.")
        return

    st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)

    # 6. Detailed Review Workspace
    st.markdown('<h3 class="section-title">📑 Human Verification Workspace</h3>', unsafe_allow_html=True)

    doc_options = {
        f"Doc #{d['id']}: {d['file_name']} — {d['employee_name']} ({d['employee_code']}) [{d['verification_status']}]": d["id"]
        for d in queue_docs
    }

    selected_doc_key = st.selectbox(
        "Select Document from Queue to Review:",
        options=list(doc_options.keys()),
        index=0
    )

    selected_doc_id = doc_options[selected_doc_key]
    doc = get_document_by_id(selected_doc_id)

    if not doc:
        st.error("Selected document could not be retrieved from database.")
        return

    # Parse JSON data safely
    try:
        extracted_fields = json.loads(doc.get("extracted_json") or "{}")
    except Exception:
        extracted_fields = {}

    try:
        comparison_data = json.loads(doc.get("comparison_json") or "{}")
    except Exception:
        comparison_data = {}

    # If comparison_data is empty, recompute live against employee profile
    if not comparison_data or "fields" not in comparison_data:
        emp_profile = {
            "name": doc.get("employee_name"),
            "email": doc.get("email"),
            "phone": doc.get("phone"),
            "department": doc.get("department"),
            "role": doc.get("role"),
            "join_date": doc.get("join_date")
        }
        comparison_data = compare_extraction_with_registration(extracted_fields, emp_profile)

    # Document Header Overview Card
    status_color = {
        "Pending HR Review": ("#fef3c7", "#b45309", "#fde68a"),
        "Approved": ("#dcfce7", "#15803d", "#bbf7d0"),
        "Rejected": ("#fee2e2", "#991b1b", "#fecaca"),
        "Correction Requested": ("#e0f2fe", "#0369a1", "#bae6fd")
    }.get(doc["verification_status"], ("#f1f5f9", "#475569", "#cbd5e1"))

    st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 1rem; margin-bottom: 1rem;">
                <div>
                    <span style="font-size: 0.8rem; font-weight: 700; color: #4F46E5; background: #EEF2FF; padding: 0.25rem 0.6rem; border-radius: 5px; border: 1px solid #C7D2FE;">
                        {doc['document_type']}
                    </span>
                    <h2 style="margin: 0.4rem 0 0.1rem 0; font-size: 1.5rem; color: #0F172A;">{doc['file_name']}</h2>
                    <span style="font-size: 0.9rem; color: #64748B;">
                        Candidate: <strong>{doc['employee_name']}</strong> ({doc['employee_code']}) • {doc['department']} • {doc['role']}
                    </span>
                </div>
                <div style="text-align: right;">
                    <span style="display: inline-block; padding: 0.4rem 0.9rem; border-radius: 9999px; font-weight: 700; font-size: 0.88rem; background: {status_color[0]}; color: {status_color[1]}; border: 1px solid {status_color[2]};">
                        Status: {doc['verification_status']}
                    </span>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 0.4rem;">
                        Uploaded: {str(doc['created_at'])[:16]}
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 1.5rem; font-size: 0.88rem; color: #475569; flex-wrap: wrap;">
                <div><strong>File Format:</strong> {doc.get('file_type') or 'N/A'}</div>
                <div><strong>File Size:</strong> {format_file_size(doc.get('file_size'))}</div>
                <div><strong>AI Engine Status:</strong> <span style="color: #4F46E5; font-weight: 600;">{doc.get('ai_status') or 'Completed'}</span></div>
                <div><strong>Last Reviewer:</strong> {doc.get('reviewed_by') or 'Pending First Review'}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Action Tabs for Document Review Workspace
    review_tab1, review_tab2, review_tab3 = st.tabs([
        "⚖️ Profile Comparison & Decision",
        "📄 Original Document & Preview",
        "📜 Audit Trail & Decision History"
    ])

    # ---------------- TAB 1: COMPARISON & DECISION ----------------
    with review_tab1:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Consistency Comparison Table
        st.markdown("##### 📊 Registration vs Document Consistency Check")
        st.markdown("<p style='font-size: 0.88rem; color: #71817D;'>Side-by-side comparison of candidate registered data vs extracted document contents.</p>", unsafe_allow_html=True)

        if "fields" in comparison_data:
            comp_rows = []
            for field_name, f_data in comparison_data["fields"].items():
                comp_rows.append({
                    "Field": f_data["label"],
                    "Registered in System": f_data["registered"],
                    "Extracted from Document": f_data["extracted"],
                    "Consistency Status": f_data["badge"],
                    "Audit Findings": f_data["notes"]
                })
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

        counts = comparison_data.get("counts", {})
        st.markdown(f"""
            <div style="display: flex; gap: 1.2rem; font-size: 0.85rem; margin-top: 0.8rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
                <span style="color: #10B981; font-weight: 600;">🟢 {counts.get('matches', 0)} Matched</span>
                <span style="color: #EF4444; font-weight: 600;">🔴 {counts.get('mismatches', 0)} Discrepancies</span>
                <span style="color: #F59E0B; font-weight: 600;">🟡 {counts.get('missing', 0)} Missing</span>
                <span style="color: #4F46E5; font-weight: 600;">ℹ️ {counts.get('manual_review', 0)} Manual Verification Needed</span>
            </div>
        """, unsafe_allow_html=True)

        # HR Decision Form
        st.markdown("<hr style='margin: 1.5rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)
        st.markdown("##### 📝 Record Binding HR Verification Decision")
        st.markdown("<p style='font-size: 0.88rem; color: #64748b;'>Select an action. Note that rejection and correction requests strictly require review notes.</p>", unsafe_allow_html=True)

        with st.form(f"hr_decision_form_{doc['id']}"):
            col_dec, col_reviewer = st.columns([2, 1])

            with col_dec:
                decision_options = ["Approved", "Rejected", "Correction Requested"]
                current_status = doc.get("verification_status")
                default_idx = decision_options.index(current_status) if current_status in decision_options else 0
                decision_choice = st.radio(
                    "HR Verification Decision *",
                    options=decision_options,
                    index=default_idx,
                    horizontal=True,
                    help="Choose explicit verification outcome"
                )

            with col_reviewer:
                reviewer_name = st.text_input(
                    "Reviewing Specialist *",
                    value=doc.get("reviewed_by") or "HR Operations Specialist",
                    help="Name and title of the authorized reviewer"
                )

            hr_notes = st.text_area(
                "Review Findings & Audit Notes * (Required for Rejections & Correction Requests)",
                value=doc.get("discrepancy_notes") or "",
                placeholder="Specify reasons for decision, documented discrepancies, or specific items candidate must re-upload...",
                help="Audit notes are permanently logged in the compliance register"
            )

            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            submit_decision = st.form_submit_button(
                "⚖️ Submit Binding HR Decision & Log Audit",
                type="primary",
                use_container_width=True
            )

        if submit_decision:
            if decision_choice in ["Rejected", "Correction Requested"] and not hr_notes.strip():
                st.error(f"❌ Review Notes are mandatory when selecting '{decision_choice}'. Please explain the discrepancy or required correction.")
            elif not reviewer_name.strip():
                st.error("❌ Reviewer name is required.")
            else:
                ok, msg = submit_hr_document_decision(
                    document_id=doc["id"],
                    decision=decision_choice,
                    review_notes=hr_notes.strip(),
                    reviewer=reviewer_name.strip()
                )

                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to submit decision: {msg}")

    # ---------------- TAB 2: ORIGINAL DOCUMENT & PREVIEW ----------------
    with review_tab2:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📥 Original File Download & Extracted Text Preview")

        file_path = doc.get("file_path")
        file_exists = file_path and os.path.exists(file_path)

        col_file_info, col_file_dl = st.columns([3, 1])

        with col_file_info:
            if file_exists:
                st.markdown(f"""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem;">
                        <strong>Physical File on Disk:</strong> <code>{file_path}</code><br/>
                        <strong>Size:</strong> {format_file_size(doc.get('file_size'))} • 
                        <strong>Format:</strong> {doc.get('file_type') or 'N/A'}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 1rem; color: #92400e;">
                        ℹ️ <strong>Database Demo Record:</strong> Stored metadata in SQLite. Original file payload was processed during intake.
                    </div>
                """, unsafe_allow_html=True)

        with col_file_dl:
            if file_exists:
                with open(file_path, "rb") as f_obj:
                    file_bytes = f_obj.read()
                st.download_button(
                    label="📥 Download Original File",
                    data=file_bytes,
                    file_name=doc["file_name"],
                    mime="application/octet-stream",
                    use_container_width=True
                )
            else:
                st.button("📥 Download Original File", disabled=True, use_container_width=True)

        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("###### 📑 Raw Extracted Document Text")
        raw_text = doc.get("extracted_text") or "No readable text content was extracted from this file."
        st.text_area(
            "raw_text_display",
            value=raw_text,
            height=260,
            disabled=True,
            label_visibility="collapsed"
        )

    # ---------------- TAB 3: AUDIT TRAIL & DECISION HISTORY ----------------
    with review_tab3:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown(f"##### 📜 Audit Trail for Document #{doc['id']} ({doc['file_name']})")
        st.markdown("<p style='font-size: 0.88rem; color: #64748b;'>Permanent compliance history documenting every review decision made on this record.</p>", unsafe_allow_html=True)

        audit_trail = get_document_audit_trail(doc["id"])

        if audit_trail:
            audit_display = []
            for a in audit_trail:
                audit_display.append({
                    "Timestamp": str(a["created_at"])[:19],
                    "Action": a["action"],
                    "Decision": a["decision"],
                    "Reviewer": a["reviewer"],
                    "Reviewer Notes": a["review_notes"] or "No notes provided",
                    "Audit Details": a["details"]
                })
            st.dataframe(pd.DataFrame(audit_display), use_container_width=True, hide_index=True)
        else:
            st.info("No prior audit logs recorded for this document. Make a decision above to log the first audit record.")

        # Global Organization Audit Log Preview
        st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)
        st.markdown("##### 🌐 Organization-Wide Compliance Review Activity")
        global_logs = get_all_audit_logs(limit=25)
        if global_logs:
            global_display = []
            for gl in global_logs:
                global_display.append({
                    "Date & Time": str(gl["created_at"])[:16],
                    "Candidate": gl["employee_name"],
                    "Document": gl.get("file_name") or f"Doc #{gl.get('document_id')}",
                    "Action": gl["action"],
                    "Decision": gl["decision"],
                    "Reviewer": gl["reviewer"],
                    "Notes": gl["review_notes"]
                })
            st.dataframe(pd.DataFrame(global_display), use_container_width=True, hide_index=True)
        else:
            st.write("No global compliance audit records yet.")
