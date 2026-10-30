"""
Employee Management module for AI-Powered Employee Onboarding System.
Provides searching, filtering, full profile inspection, profile editing,
status updating, and safe deletion with cascade cleanup of tasks and documents.
"""

from datetime import datetime
import streamlit as st
import pandas as pd
from config import REPORTING_MANAGERS
from database.db import (
    get_all_employees,
    get_employee_by_id,
    get_employee_tasks,
    get_employee_documents,
    update_employee,
    update_employee_status,
    delete_employee,
    get_all_departments,
    get_all_statuses
)


def render_employee_management():
    """Renders the Employee Directory and Management interface."""

    # 1. Header Banner
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">📁 Employee Directory & Management</h1>
            <p class="header-subtitle">
                Search, inspect complete candidate profiles, update onboarding statuses, edit workforce records,
                and manage the new hire lifecycle across all departments.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Informational Callout
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ Data Governance & Integrity:</strong> All profile edits update the central relational store in real time.
            Employee deletions are handled within a strict database transaction, cleanly removing associated checklist tasks
            and documents to avoid orphaned records.
        </div>
    """, unsafe_allow_html=True)

    # 3. Search & Filter Bar
    st.markdown('<h3 class="section-title">🔍 Search & Filter Workforce</h3>', unsafe_allow_html=True)

    col_search, col_dept, col_status = st.columns([2, 1, 1])

    with col_search:
        search_query = st.text_input(
            "Search Candidates",
            placeholder="Search by name, email, or employee ID (e.g. EMP-1001)...",
            label_visibility="collapsed"
        )

    with col_dept:
        dept_options = ["All Departments"] + get_all_departments()
        selected_dept = st.selectbox(
            "Department Filter",
            options=dept_options,
            label_visibility="collapsed"
        )

    with col_status:
        status_options = ["All Statuses"] + get_all_statuses()
        selected_status = st.selectbox(
            "Status Filter",
            options=status_options,
            label_visibility="collapsed"
        )

    # 4. Fetch Employees based on Filters
    employees = get_all_employees(
        search_term=search_query,
        department=selected_dept,
        status=selected_status
    )

    # Summary metric bar
    total_matching = len(employees)
    st.markdown(f"""
        <div style="font-size: 0.88rem; color: #64748b; margin-top: -0.2rem; margin-bottom: 1rem;">
            Showing <strong>{total_matching}</strong> employee{'s' if total_matching != 1 else ''} matching current criteria.
        </div>
    """, unsafe_allow_html=True)

    # 5. Interactive Employee Roster Table
    if employees:
        roster_data = []
        for emp in employees:
            total_t = emp.get("total_tasks", 0)
            completed_t = emp.get("completed_tasks", 0)
            pct = int((completed_t / total_t * 100)) if total_t > 0 else 0
            roster_data.append({
                "ID": emp["employee_code"],
                "Full Name": emp["name"],
                "Email": emp["email"],
                "Department": emp["department"],
                "Job Role": emp["role"],
                "Location": emp.get("work_location") or "HQ",
                "Start Date": emp["join_date"],
                "Status": emp["status"],
                "Onboarding Progress": f"{completed_t}/{total_t} ({pct}%)" if total_t > 0 else "0/0 (0%)"
            })

        df_roster = pd.DataFrame(roster_data)
        st.dataframe(
            df_roster,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No employees found matching the search and filter criteria.")
        return

    st.markdown("<hr style='margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)

    # 6. Detailed Profile Inspection & Management Workspace
    st.markdown('<h3 class="section-title">👤 Employee Profile & Actions Workspace</h3>', unsafe_allow_html=True)

    # Build dropdown options mapping
    employee_options = {
        f"{emp['employee_code']} — {emp['name']} ({emp['department']})": emp['id']
        for emp in employees
    }
    
    selected_label = st.selectbox(
        "Select Employee to View / Edit:",
        options=list(employee_options.keys()),
        index=0
    )

    selected_emp_id = employee_options[selected_label]
    current_emp = get_employee_by_id(selected_emp_id)

    if not current_emp:
        st.error("Selected employee record could not be loaded from database.")
        return

    # Tabs for Profile View, Edit Profile, and Delete Employee
    tab_view, tab_edit, tab_delete = st.tabs([
        "📋 Complete Profile & Progress",
        "✏️ Edit Information",
        "🗑️ Delete Employee (Danger Zone)"
    ])

    # ---------------- TAB 1: COMPLETE PROFILE & PROGRESS ----------------
    with tab_view:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Profile Summary Card
        total_tasks = current_emp.get("total_tasks", 0)
        completed_tasks = current_emp.get("completed_tasks", 0)
        progress_pct = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0

        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 1rem; margin-bottom: 1.2rem;">
                    <div>
                        <span style="background: #EEF2FF; color: #4F46E5; font-weight: 700; font-size: 0.85rem; padding: 0.3rem 0.7rem; border-radius: 6px; border: 1px solid #C7D2FE;">
                            {current_emp['employee_code']}
                        </span>
                        <h2 style="margin: 0.4rem 0 0.1rem 0; font-size: 1.6rem; color: #0F172A; font-weight: 700;">
                            {current_emp['name']}
                        </h2>
                        <span style="font-size: 0.95rem; color: #64748B; font-weight: 500;">
                            {current_emp['role']} • {current_emp['department']}
                        </span>
                    </div>
                    <div style="text-align: right;">
                        <span style="display: inline-block; padding: 0.4rem 0.9rem; border-radius: 9999px; font-weight: 700; font-size: 0.88rem; background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;">
                            Status: {current_emp['status']}
                        </span>
                    </div>
                </div>

                <div style="margin-bottom: 1.2rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; color: #64748B; margin-bottom: 0.4rem;">
                        <span>Overall Onboarding Progress</span>
                        <span>{completed_tasks} of {total_tasks} Milestones Completed ({progress_pct}%)</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.progress(progress_pct / 100.0)

        # Profile Metadata Grid
        col_meta1, col_meta2 = st.columns(2)

        with col_meta1:
            st.markdown("""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; height: 100%; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);">
                    <h4 style="margin: 0 0 0.8rem 0; font-size: 0.95rem; color: #0F172A; text-transform: uppercase; letter-spacing: 0.05em;">
                        📍 Contact & Location
                    </h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.9rem; color: #334155;">
                        <div><strong>Email:</strong> {email}</div>
                        <div><strong>Phone:</strong> {phone}</div>
                        <div><strong>Work Location:</strong> {location}</div>
                        <div><strong>Joining Date:</strong> {join_date}</div>
                    </div>
                </div>
            """.format(
                email=current_emp.get("email", "N/A"),
                phone=current_emp.get("phone", "N/A"),
                location=current_emp.get("work_location") or "Not Specified",
                join_date=current_emp.get("join_date", "N/A")
            ), unsafe_allow_html=True)

        with col_meta2:
            st.markdown("""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; height: 100%; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);">
                    <h4 style="margin: 0 0 0.8rem 0; font-size: 0.95rem; color: #0F172A; text-transform: uppercase; letter-spacing: 0.05em;">
                        🏢 Organizational Details
                    </h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.9rem; color: #334155;">
                        <div><strong>Department:</strong> {dept}</div>
                        <div><strong>Job Role:</strong> {role}</div>
                        <div><strong>Reporting Manager:</strong> {manager}</div>
                        <div><strong>Registered In System:</strong> {created_at}</div>
                    </div>
                </div>
            """.format(
                dept=current_emp.get("department", "N/A"),
                role=current_emp.get("role", "N/A"),
                manager=current_emp.get("reporting_manager") or "Not Assigned",
                created_at=str(current_emp.get("created_at", "N/A"))[:19]
            ), unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

        # Onboarding Checklist Preview
        tasks = get_employee_tasks(selected_emp_id)
        with st.expander(f"📋 View Onboarding Tasks ({len(tasks)} assigned)", expanded=True):
            if tasks:
                tasks_df = pd.DataFrame([
                    {
                        "Task Description": t["task_title"],
                        "Category": t["category"],
                        "Status": "✅ Completed" if t["is_completed"] == 1 else "⏳ Incomplete",
                        "Due Date": t.get("due_date") or "Onboarding Period"
                    }
                    for t in tasks
                ])
                st.dataframe(tasks_df, use_container_width=True, hide_index=True)
            else:
                st.write("No checklist tasks assigned to this employee.")

        # Associated Documents Queue Preview
        docs = get_employee_documents(selected_emp_id)
        with st.expander(f"📄 View Associated Documents ({len(docs)} files)"):
            if docs:
                docs_df = pd.DataFrame([
                    {
                        "Document Type": d["document_type"],
                        "File Name": d["file_name"] or "Uploaded File",
                        "HR Verification Status": d["verification_status"],
                        "Notes": d.get("discrepancy_notes") or "None"
                    }
                    for d in docs
                ])
                st.dataframe(docs_df, use_container_width=True, hide_index=True)
            else:
                st.write("No documents uploaded for this employee yet.")

    # ---------------- TAB 2: EDIT INFORMATION ----------------
    with tab_edit:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("##### ✏️ Update Profile & Onboarding Status")
        st.markdown("<p style='font-size: 0.88rem; color: #64748b;'>Modify profile fields and click save to persist changes immediately to the SQLite database.</p>", unsafe_allow_html=True)

        with st.form(f"edit_employee_form_{selected_emp_id}"):
            col_edit1, col_edit2 = st.columns(2)

            with col_edit1:
                edit_name = st.text_input("Full Name *", value=current_emp.get("name", ""))
                edit_email = st.text_input("Work Email *", value=current_emp.get("email", ""))
                edit_phone = st.text_input("Phone Number", value=current_emp.get("phone", ""))

                location_options = [
                    "San Francisco, CA (HQ)",
                    "New York, NY",
                    "Austin, TX",
                    "London, UK",
                    "Remote - US",
                    "Remote - International",
                    "Other"
                ]
                current_loc = current_emp.get("work_location") or "San Francisco, CA (HQ)"
                loc_index = location_options.index(current_loc) if current_loc in location_options else 0
                edit_location = st.selectbox("Work Location", options=location_options, index=loc_index)

            with col_edit2:
                all_depts = get_all_departments()
                current_dept = current_emp.get("department", all_depts[0])
                dept_index = all_depts.index(current_dept) if current_dept in all_depts else 0
                edit_dept = st.selectbox("Department *", options=all_depts, index=dept_index)

                edit_role = st.text_input("Job Role *", value=current_emp.get("role", ""))
                
                cur_manager = current_emp.get("reporting_manager", "")
                manager_options = list(REPORTING_MANAGERS)
                if cur_manager and cur_manager not in manager_options:
                    manager_options.insert(0, cur_manager)
                mgr_index = manager_options.index(cur_manager) if cur_manager in manager_options else 0
                edit_manager = st.selectbox("Reporting Manager *", options=manager_options, index=mgr_index)

                # Parse date safely
                try:
                    default_date = datetime.strptime(current_emp.get("join_date", "2026-11-01"), "%Y-%m-%d").date()
                except Exception:
                    default_date = datetime.now().date()

                edit_join_date = st.date_input("Joining Date *", value=default_date)

                status_choices = ["In Progress", "Pending HR Review", "Completed", "On Hold"]
                cur_status = current_emp.get("status", "In Progress")
                status_index = status_choices.index(cur_status) if cur_status in status_choices else 0
                edit_status = st.selectbox("Onboarding Status *", options=status_choices, index=status_index)

            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            submit_edit = st.form_submit_button("💾 Save Profile Updates", type="primary", use_container_width=True)

        if submit_edit:
            updated_payload = {
                "name": edit_name.strip(),
                "email": edit_email.strip().lower(),
                "phone": edit_phone.strip(),
                "department": edit_dept,
                "role": edit_role.strip(),
                "join_date": str(edit_join_date),
                "reporting_manager": edit_manager.strip(),
                "work_location": edit_location,
                "status": edit_status
            }

            success, message = update_employee(selected_emp_id, updated_payload)
            if success:
                st.success(f"✅ Success: {message}")
                st.rerun()
            else:
                st.error(f"❌ Error updating employee: {message}")

    # ---------------- TAB 3: DANGER ZONE (DELETE EMPLOYEE) ----------------
    with tab_delete:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("""
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-left: 5px solid #ef4444; border-radius: 10px; padding: 1.2rem; margin-bottom: 1.5rem;">
                <div style="font-size: 1.1rem; font-weight: 700; color: #991b1b; margin-bottom: 0.4rem;">
                    ⚠️ Warning: Irreversible Employee Deletion
                </div>
                <p style="font-size: 0.9rem; color: #7f1d1d; margin: 0 0 0.8rem 0;">
                    Deleting <strong>{name}</strong> (<strong>{code}</strong>) will permanently remove this record
                    from the database. All <strong>associated checklist tasks</strong> and <strong>uploaded documents</strong>
                    will be deleted simultaneously in a database transaction to ensure no orphaned data remains.
                </p>
                <div style="font-size: 0.85rem; color: #991b1b;">
                    This action cannot be undone.
                </div>
            </div>
        """.format(
            name=current_emp['name'],
            code=current_emp['employee_code']
        ), unsafe_allow_html=True)

        confirm_checkbox = st.checkbox(
            f"I confirm that I want to permanently delete {current_emp['name']} ({current_emp['employee_code']}) and all associated records."
        )

        if st.button("🗑️ Permanently Delete Employee", type="secondary", disabled=not confirm_checkbox):
            success, message = delete_employee(selected_emp_id)
            if success:
                st.success(f"✅ {message}")
                st.rerun()
            else:
                st.error(f"❌ Failed to delete employee: {message}")
