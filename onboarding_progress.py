"""
Onboarding Progress Tracking module for OnboardAI.
Provides a centralized dashboard for HR to monitor each employee's onboarding journey,
including overall statistics, searchable employee table, stage‑wise status, pending
activities and overdue checklist tasks.

All calculations reuse existing database helpers in `database.db` – no duplicate
records are created.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any
from database.db import (
    get_all_employees,
    get_employee_by_id,
    get_employee_tasks,
    get_employee_documents,
    get_overdue_checklist_tasks,
    get_all_departments,
)
from datetime import datetime, date

# Database helpers
from database.db import (
    get_all_employees,
    get_employee_by_id,
    get_employee_tasks,
    get_employee_documents,
    get_overdue_checklist_tasks,
)

# ---------------------------------------------------------------------------
# Helper: compute stage‑wise status for a single employee record.
# ---------------------------------------------------------------------------
def _compute_employee_stages(employee: dict) -> dict:
    """Return a dictionary with stage flags and an overall completion percent.

    Stages:
    1. Registration – always true because the employee record exists.
    2. Document Submission – any document rows for the employee.
    3. HR Document Review – at least one document with verification_status !=
       'Pending HR Review'.
    4. Smart Checklist – checklist tasks exist (total_tasks > 0).
    5. Overall Completion – status == "Completed" **and** all checklist tasks
       are marked completed.
    """
    employee_id = employee["id"]
    # Stage 1 – registration
    stage_registration = True

    # Stage 2 – document submission
    docs = get_employee_documents(employee_id)
    stage_documents = len(docs) > 0

    # Stage 3 – HR review (at least one document reviewed)
    stage_hr_review = any(
        d.get("verification_status") != "Pending HR Review" for d in docs
    )

    # Stage 4 – checklist tasks existence
    tasks = get_employee_tasks(employee_id)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.get("is_completed"))
    stage_checklist = total_tasks > 0

    # Stage 5 – overall completion
    # Employee is considered fully onboarded when:
    #   * status field is "Completed"
    #   * all checklist tasks are completed
    #   * there is at least one approved document (i.e., HR review passed)
    overall_completed = (
        employee.get("status") == "Completed"
        and total_tasks > 0
        and completed_tasks == total_tasks
        and any(d.get("verification_status") == "Approved" for d in docs)
    )

    # Compute a simple percentage – each of the four dynamic stages contributes
    # equally (25 %). Registration is implicit and always counted.
    completed_stage_cnt = sum(
        [stage_documents, stage_hr_review, stage_checklist, overall_completed]
    )
    progress_pct = int((completed_stage_cnt / 4) * 100)

    return {
        "stage_registration": stage_registration,
        "stage_documents": stage_documents,
        "stage_hr_review": stage_hr_review,
        "stage_checklist": stage_checklist,
        "overall_completed": overall_completed,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "progress_pct": progress_pct,
        "documents": docs,
        "tasks": tasks,
    }

# ---------------------------------------------------------------------------
# UI Rendering
# ---------------------------------------------------------------------------
def render_onboarding_progress():
    """Render the full onboarding progress view.

    The layout mirrors the existing HR Dashboard – a metrics row, filter/search
    controls, a searchable employee table and a detailed side‑panel that appears
    when a row is selected.
    """
    st.markdown(
        """
        <div class="header-container">
            <h1 class="header-title">📈 Employee Onboarding Progress</h1>
            <p class="header-subtitle">Monitor individual onboarding milestones, pending documents and overdue tasks.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------
    # 1️⃣ Summary metrics (reuse dashboard counts where possible)
    # -------------------------------------------------------------------
    all_emps = get_all_employees()
    total_employees = len(all_emps)
    completed_onboardings = sum(1 for e in all_emps if e.get("status") == "Completed")
    in_progress = total_employees - completed_onboardings
    pending_docs = sum(e.get("pending_docs", 0) for e in all_emps)
    overdue_tasks = len(get_overdue_checklist_tasks())

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="stat-card blue">
            <div class="stat-title">Total Employees</div>
            <div class="stat-value">{total_employees}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card emerald">
            <div class="stat-title">Completed</div>
            <div class="stat-value">{completed_onboardings}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="stat-card amber">
            <div class="stat-title">In‑Progress</div>
            <div class="stat-value">{in_progress}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="stat-card rose">
            <div class="stat-title">Pending Docs</div>
            <div class="stat-value">{pending_docs}</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="stat-card purple">
            <div class="stat-title">Overdue Tasks</div>
            <div class="stat-value">{overdue_tasks}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------------
    # 2️⃣ Filters & Search
    # -------------------------------------------------------------------
    col_search, col_dept, col_status = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input("Search", placeholder="Name, Email or Employee ID")
    with col_dept:
        dept_options = ["All Departments"] + get_all_departments()
        selected_dept = st.selectbox("Department", options=dept_options)
    with col_status:
        status_options = ["All Statuses"] + ["In Progress", "Completed", "Pending HR Review", "On Hold"]
        selected_status = st.selectbox("Status", options=status_options)

    # Apply filters
    filtered = []
    for emp in all_emps:
        if search_query and search_query.lower() not in (
            emp["name"].lower() + emp["email"].lower() + emp["employee_code"].lower()
        ):
            continue
        if selected_dept != "All Departments" and emp["department"] != selected_dept:
            continue
        if selected_status != "All Statuses" and emp["status"] != selected_status:
            continue
        filtered.append(emp)

    # -------------------------------------------------------------------
    # 3️⃣ Employee table
    # -------------------------------------------------------------------
    if not filtered:
        st.info("No employees match the current filters.")
        return

    # Enrich rows with progress percentage for display
    table_data = []
    progress_cache = {}
    for emp in filtered:
        stages = _compute_employee_stages(emp)
        progress_cache[emp["id"]] = stages
        pct = stages["progress_pct"]
        table_data.append(
            {
                "ID": emp["employee_code"],
                "Name": emp["name"],
                "Department": emp["department"],
                "Role": emp["role"],
                "Start": emp["join_date"],
                "Status": emp["status"],
                "Progress": f"{pct}%",
            }
        )
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------
    # 4️⃣ Detail pane – select via a dropdown of IDs (simpler than row click)
    # -------------------------------------------------------------------
    st.markdown("---")
    emp_options = {f"{e['employee_code']} – {e['name']}": e["id"] for e in filtered}
    selected_key = st.selectbox("Select employee for detailed view", options=list(emp_options.keys()))
    selected_id = emp_options[selected_key]
    emp_record = get_employee_by_id(selected_id)
    if not emp_record:
        st.error("Unable to load employee details.")
        return

    stages = progress_cache.get(selected_id) or _compute_employee_stages(emp_record)

    # -------------------------------------------------------------------
    # 5️⃣ Detailed view layout
    # -------------------------------------------------------------------
    st.subheader(f"{emp_record['employee_code']} – {emp_record['name']}")
    col_left, col_right = st.columns([2, 1])
    with col_left:
        # Profile card
        st.markdown(
            f"""
            <div style="background:#ffffff;border:1px solid #E2E8F0;border-radius:10px;padding:1.2rem;margin-bottom:1rem;box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);">
                <h3 style="color:#0F172A;margin-top:0;">{emp_record['name']}</h3>
                <p style="color:#334155;margin:0.3rem 0;"><strong>Department:</strong> {emp_record['department']}</p>
                <p style="color:#334155;margin:0.3rem 0;"><strong>Role:</strong> {emp_record['role']}</p>
                <p style="color:#334155;margin:0.3rem 0;"><strong>Start Date:</strong> {emp_record['join_date']}</p>
                <p style="color:#334155;margin:0.3rem 0;"><strong>Status:</strong> <span style="background:#FFFBEB;color:#D97706;padding:2px 8px;border-radius:4px;font-weight:600;border:1px solid #FDE68A;">{emp_record['status']}</span></p>
                <p style="color:#4F46E5;margin:0.3rem 0;font-weight:700;"><strong>Overall Progress:</strong> {stages['progress_pct']}%</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Stage‑wise status list
        st.markdown("**Stage‑wise Status**")
        stage_table = pd.DataFrame(
            [
                {"Stage": "Employee Registration", "Completed": "✅" if stages["stage_registration"] else "❌"},
                {"Stage": "Document Submission", "Completed": "✅" if stages["stage_documents"] else "❌"},
                {"Stage": "HR Document Review", "Completed": "✅" if stages["stage_hr_review"] else "❌"},
                {"Stage": "Smart Checklist", "Completed": "✅" if stages["stage_checklist"] else "❌"},
                {"Stage": "Overall Completion", "Completed": "✅" if stages["overall_completed"] else "❌"},
            ]
        )
        st.table(stage_table)

        # Pending activities
        pending_docs = [d for d in stages["documents"] if d.get("verification_status") == "Pending HR Review"]
        pending_tasks = [t for t in stages["tasks"] if not t.get("is_completed")]
        st.markdown("**Pending Activities**")
        if pending_docs:
            st.write("Documents awaiting HR review:")
            for d in pending_docs:
                st.write(f"- {d.get('document_type')}: {d.get('file_name')}")
        if pending_tasks:
            st.write("Checklist tasks not yet done:")
            for t in pending_tasks:
                due = t.get("due_date")
                overdue = due and date.fromisoformat(due) < date.today()
                badge = "⚠️ Overdue" if overdue else ""
                st.write(f"- {t.get('task_title')} {badge}")
        if not pending_docs and not pending_tasks:
            st.success("No pending activities.")

        # Completed activities
        st.markdown("**Completed Activities**")
        completed_docs = [d for d in stages["documents"] if d.get("verification_status") == "Approved"]
        completed_tasks = [t for t in stages["tasks"] if t.get("is_completed")]
        if completed_docs:
            st.write("Approved documents:")
            for d in completed_docs:
                st.write(f"- {d.get('document_type')}: {d.get('file_name')}")
        if completed_tasks:
            st.write("Finished checklist items:")
            for t in completed_tasks:
                st.write(f"- {t.get('task_title')} (completed {t.get('completed_at')})")
        if not completed_docs and not completed_tasks:
            st.info("No completed items yet.")

    with col_right:
        # Overdue tasks table (if any)
        overdue = [t for t in stages["tasks"] if not t.get("is_completed") and t.get("due_date") and date.fromisoformat(t.get("due_date")) < date.today()]
        if overdue:
            st.markdown("### Overdue Checklist Tasks")
            overdue_df = pd.DataFrame(
                [
                    {
                        "Task": t["task_title"],
                        "Due": t["due_date"],
                        "Category": t["category"],
                    }
                    for t in overdue
                ]
            )
            st.table(overdue_df)
        else:
            st.success("No overdue tasks.")

    # -------------------------------------------------------------------
    # 6️⃣ Timeline – combine key timestamps from registration, docs, reviews, tasks
    # -------------------------------------------------------------------
    st.markdown("---")
    st.subheader("Chronological Timeline")
    timeline_events = []
    # Registration (created_at)
    if emp_record.get("created_at"):
        timeline_events.append((emp_record["created_at"], "Employee record created (registration)"))
    # Document uploads & reviews
    for doc in stages["documents"]:
        if doc.get("created_at"):
            timeline_events.append((doc["created_at"], f"Document uploaded: {doc.get('document_type')}"))
        if doc.get("reviewed_at"):
            timeline_events.append((doc["reviewed_at"], f"HR {doc.get('verification_status')} for {doc.get('document_type')}"))
    # Checklist completions
    for t in stages["tasks"]:
        if t.get("completed_at"):
            timeline_events.append((t["completed_at"], f"Task completed: {t.get('task_title')}"))
        elif t.get("due_date"):
            # add a due date reminder event (optional)
            timeline_events.append((t["due_date"], f"Task due: {t.get('task_title')}"))
    # Sort chronological
    timeline_events.sort(key=lambda x: x[0])
    for ts, desc in timeline_events:
        # Convert iso/auto timestamps to readable date
        try:
            # SQLite timestamps are stored as ISO strings
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(ts)
        st.write(f"- **{date_str}** – {desc}")

# End of module
