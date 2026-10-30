"""
Smart Onboarding Checklist module for AI-Powered Employee Onboarding System.
Provides per-employee task management: view, add, complete/undo, delete checklist tasks.
Displays progress bars, category grouping, and an overview table across all employees.
"""

import streamlit as st
from database.db import (
    get_all_employees,
    get_employee_by_id,
    get_employee_tasks,
    add_checklist_task,
    toggle_checklist_task,
    delete_checklist_task,
    get_checklist_summary_all_employees,
    get_task_categories,
)


# ── Helper: Progress bar HTML ──────────────────────────────────────────────────

def _progress_bar_html(completed: int, total: int) -> str:
    """Returns an HTML progress bar string for checklist completion."""
    if total == 0:
        pct = 0
    else:
        pct = int((completed / total) * 100)

    if pct == 100:
        color = "#10B981"   # emerald
    elif pct >= 50:
        color = "#4F46E5"   # indigo
    else:
        color = "#F59E0B"   # amber

    return f"""
        <div style="display:flex; align-items:center; gap:0.6rem;">
            <div style="flex:1; background:#EEF2FF; border-radius:999px; height:10px; overflow:hidden;">
                <div style="width:{pct}%; background:{color}; height:100%; border-radius:999px; transition:width 0.3s;"></div>
            </div>
            <span style="font-size:0.8rem; font-weight:600; color:#64748B; min-width:40px;">{completed}/{total}</span>
        </div>
    """


def _status_badge(status: str) -> str:
    """Returns a styled HTML badge for employee onboarding status."""
    colors = {
        "Completed":        ("#ECFDF5", "#059669"),
        "In Progress":      ("#EFF6FF", "#2563EB"),
        "Pending HR Review":("#FFFBEB", "#D97706"),
        "On Hold":          ("#F1F5F9", "#475569"),
    }
    bg, fg = colors.get(status, ("#F8FAFC", "#334155"))
    return (
        f'<span style="background:{bg}; color:{fg}; padding:2px 10px; border-radius:999px; '
        f'font-size:0.78rem; font-weight:600; border: 1px solid #E2E8F0;">{status}</span>'
    )


# ── Sub-view: Employee Checklist Detail ────────────────────────────────────────

def _render_employee_checklist(employee: dict):
    """Renders the detailed checklist for a single employee."""

    emp_id   = employee["id"]
    emp_name = employee["name"]
    emp_code = employee["employee_code"]

    # ── Employee header (Light, modern card) ──
    st.markdown(f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:5px solid #4F46E5;
                    padding:1.2rem 1.5rem; border-radius:12px; margin-bottom:1.5rem;
                    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);">
            <div style="font-size:1.35rem; font-weight:700; color:#0F172A;">{emp_name}</div>
            <div style="font-size:0.88rem; color:#64748B; margin-top:0.2rem;">
                {emp_code} &nbsp;•&nbsp; {employee.get('department','—')} &nbsp;•&nbsp; {employee.get('role','—')}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Progress summary ──
    tasks = get_employee_tasks(emp_id)
    total     = len(tasks)
    completed = sum(1 for t in tasks if t["is_completed"])
    pending   = total - completed

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Tasks", total)
    with c2:
        st.metric("Completed", completed)
    with c3:
        st.metric("Remaining", pending)

    if total > 0:
        st.markdown(_progress_bar_html(completed, total), unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
    else:
        st.info("No tasks assigned yet. Add a task below.")

    # ── Tasks grouped by category ──
    if tasks:
        categories = sorted(list({t["category"] for t in tasks}))
        for cat in categories:
            cat_tasks = [t for t in tasks if t["category"] == cat]
            cat_done  = sum(1 for t in cat_tasks if t["is_completed"])

            st.markdown(f"""
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
                            padding:0.9rem 1.1rem; margin-bottom:0.5rem;">
                    <div style="font-weight:700; color:#1e293b; font-size:0.95rem;">
                        📂 {cat}
                        <span style="font-size:0.8rem; color:#64748b; font-weight:400;
                                     margin-left:0.5rem;">({cat_done}/{len(cat_tasks)} done)</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            for task in cat_tasks:
                task_id   = task["id"]
                is_done   = bool(task["is_completed"])
                due_label = f" — Due: {task['due_date']}" if task.get("due_date") else ""
                done_label= f" ✓ Done: {task['completed_at'][:10] if task.get('completed_at') else ''}" if is_done else ""

                col_check, col_label, col_del = st.columns([0.08, 0.78, 0.14])

                with col_check:
                    new_state = st.checkbox(
                        "done",
                        value=is_done,
                        key=f"task_cb_{task_id}",
                        label_visibility="collapsed"
                    )
                    if new_state != is_done:
                        ok, msg = toggle_checklist_task(task_id, new_state)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)

                with col_label:
                    title_style = "text-decoration:line-through; color:#94a3b8;" if is_done else "color:#1e293b;"
                    st.markdown(
                        f'<span style="font-size:0.9rem; {title_style}">{task["task_title"]}</span>'
                        f'<span style="font-size:0.78rem; color:#94a3b8;">{due_label}{done_label}</span>',
                        unsafe_allow_html=True
                    )

                with col_del:
                    if st.button("🗑️", key=f"del_task_{task_id}", help="Delete this task"):
                        ok, msg = delete_checklist_task(task_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("---")

    # ── Add new task form ──
    st.markdown("#### ➕ Add a New Task")
    with st.form(key=f"add_task_form_{emp_id}", clear_on_submit=True):
        col_a, col_b = st.columns([2, 1])
        with col_a:
            new_title = st.text_input("Task Title *", placeholder="e.g. Complete NDA Signing")
        with col_b:
            all_cats  = get_task_categories()
            new_cat   = st.selectbox("Category *", options=all_cats)

        col_c, col_d = st.columns([1, 1])
        with col_c:
            new_due = st.date_input("Due Date (optional)", value=None)
        with col_d:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Add Task", use_container_width=True)

        if submitted:
            due_str = str(new_due) if new_due else None
            ok, msg = add_checklist_task(emp_id, new_title, new_cat, due_str)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ── Sub-view: Overview Table ───────────────────────────────────────────────────

def _render_overview_table():
    """Renders the all-employees checklist summary overview."""

    summaries = get_checklist_summary_all_employees()

    if not summaries:
        st.info("No employees registered yet. Register an employee to begin.")
        return

    st.markdown("#### 👥 All Employees — Checklist Progress")

    for emp in summaries:
        total     = emp["total_tasks"]
        completed = emp["completed_tasks"]
        pending   = emp["pending_tasks"]
        pct       = int((completed / total) * 100) if total > 0 else 0

        with st.container():
            st.markdown(f"""
                <div style="background:#fff; border:1px solid #e2e8f0; border-radius:10px;
                            padding:0.9rem 1.2rem; margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-weight:700; color:#1e293b;">{emp['name']}</span>
                            <span style="font-size:0.8rem; color:#64748b; margin-left:0.5rem;">
                                {emp['employee_code']} &nbsp;•&nbsp; {emp['department']}
                            </span>
                        </div>
                        {_status_badge(emp['status'])}
                    </div>
                    <div style="margin-top:0.5rem;">
                        {_progress_bar_html(completed, total)}
                    </div>
                    <div style="font-size:0.78rem; color:#94a3b8; margin-top:0.3rem;">
                        {completed} completed &nbsp;•&nbsp; {pending} remaining &nbsp;•&nbsp; {pct}% done
                    </div>
                </div>
            """, unsafe_allow_html=True)


# ── Main render function ───────────────────────────────────────────────────────

def render_smart_checklist():
    """Renders the Smart Onboarding Checklist module."""

    # 1. Header
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">✅ Smart Onboarding Checklist</h1>
            <p class="header-subtitle">
                Track, manage, and complete per-employee onboarding milestones.
                Add tasks, mark completions, and monitor progress across the entire workforce.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Mode selector
    view_mode = st.radio(
        "View Mode",
        options=["Employee Checklist", "All Employees Overview"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("---")

    # ── All Employees Overview ──
    if view_mode == "All Employees Overview":
        _render_overview_table()
        return

    # ── Per-Employee Checklist ──
    all_employees = get_all_employees()

    if not all_employees:
        st.warning("No employees registered. Go to **Employee Registration** to add the first new hire.")
        return

    # Build employee selector options: "EMP-1001 — Sarah Jenkins (Engineering)"
    emp_options = {
        f"{e['employee_code']} — {e['name']} ({e['department']})": e["id"]
        for e in all_employees
    }

    selected_label = st.selectbox(
        "Select Employee",
        options=list(emp_options.keys()),
        help="Choose the employee whose checklist you want to view or manage."
    )

    if not selected_label:
        st.info("Select an employee above to view their checklist.")
        return

    emp_id   = emp_options[selected_label]
    employee = next((e for e in all_employees if e["id"] == emp_id), None)

    if not employee:
        st.error("Employee not found. Please refresh the page.")
        return

    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
    _render_employee_checklist(employee)
