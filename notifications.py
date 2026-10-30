"""
Notifications & Reminders module for OnboardAI (Stage 9).
Provides a centralized notification center for HR to track pending onboarding activities,
including document verification requests, overdue milestones, upcoming deadlines,
and incomplete onboarding processes.
"""

from datetime import datetime, date
from typing import Dict, List, Any, Optional
import streamlit as st
import pandas as pd

from database.db import (
    sync_system_notifications,
    get_all_notifications,
    get_notification_metrics,
    mark_notification_status,
    mark_all_notifications_status,
    delete_notification,
    clear_all_notifications,
    get_employee_by_id,
    DEFAULT_NOTIFICATION_PRIORITIES
)


def get_priority_badge(priority: str) -> str:
    """Returns an HTML badge for notification priority."""
    p_lower = (priority or "").lower()
    if p_lower == "high":
        return '<span style="background: #FEF2F2; color: #DC2626; font-weight: 700; font-size: 0.78rem; padding: 0.2rem 0.6rem; border-radius: 9999px; border: 1px solid #FECACA;">🔴 High</span>'
    elif p_lower == "medium":
        return '<span style="background: #FFFBEB; color: #D97706; font-weight: 700; font-size: 0.78rem; padding: 0.2rem 0.6rem; border-radius: 9999px; border: 1px solid #FDE68A;">🟡 Medium</span>'
    else:
        return '<span style="background: #EFF6FF; color: #2563EB; font-weight: 700; font-size: 0.78rem; padding: 0.2rem 0.6rem; border-radius: 9999px; border: 1px solid #BFDBFE;">🔵 Low</span>'


def get_category_badge(category: str) -> str:
    """Returns an HTML badge for notification category."""
    cat_lower = (category or "").lower()
    if "document" in cat_lower and "review" in cat_lower:
        return '<span style="background: #F8FAFC; color: #334155; font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 6px; border: 1px solid #E2E8F0;">📑 Document Review</span>'
    elif "checklist" in cat_lower or "milestone" in cat_lower:
        return '<span style="background: #F8FAFC; color: #334155; font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 6px; border: 1px solid #E2E8F0;">✅ Checklist Milestone</span>'
    elif "submission" in cat_lower:
        return '<span style="background: #F8FAFC; color: #334155; font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 6px; border: 1px solid #E2E8F0;">📤 Document Submission</span>'
    else:
        return '<span style="background: #F8FAFC; color: #334155; font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 6px; border: 1px solid #E2E8F0;">ℹ️ General Onboarding</span>'


def render_notifications():
    """Renders the Centralized Notification and Reminder Center."""

    # 1. Header Banner
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">🔔 Notifications & Reminder Center</h1>
            <p class="header-subtitle">
                Centralized HR intelligence dashboard for tracking urgent document verification reviews,
                overdue onboarding milestones, upcoming compliance deadlines, and candidate reminders.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Key Guardrail Policy Callout
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ Compliance & SLA Management:</strong> High-priority alerts require timely HR intervention.
            Automated alerts are synchronized with real-time database state and deduplicated to prevent repetitive notices.
        </div>
    """, unsafe_allow_html=True)

    # 3. Session State for Configurable Rules
    if "notif_priority_rules" not in st.session_state:
        st.session_state["notif_priority_rules"] = dict(DEFAULT_NOTIFICATION_PRIORITIES)
    if "upcoming_deadline_days" not in st.session_state:
        st.session_state["upcoming_deadline_days"] = 7

    # Run deduplicated background sync
    sync_system_notifications(
        priority_rules=st.session_state["notif_priority_rules"],
        upcoming_days=st.session_state["upcoming_deadline_days"]
    )

    # 4. Metric Headline Cards
    metrics = get_notification_metrics()

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.markdown(f"""
            <div class="stat-card blue">
                <div class="stat-title">Total Notifications</div>
                <div class="stat-value">{metrics['total']}</div>
                <div class="stat-subtext">📋 Active system alerts</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col2:
        st.markdown(f"""
            <div class="stat-card amber">
                <div class="stat-title">Unread Alerts</div>
                <div class="stat-value">{metrics['unread']}</div>
                <div class="stat-subtext">📬 Awaiting HR attention</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col3:
        st.markdown(f"""
            <div class="stat-card rose">
                <div class="stat-title">High Priority</div>
                <div class="stat-value">{metrics['high_priority']}</div>
                <div class="stat-subtext">🚨 Urgent approvals & deadlines</div>
            </div>
        """, unsafe_allow_html=True)

    with m_col4:
        st.markdown(f"""
            <div class="stat-card purple">
                <div class="stat-title">Overdue Activities</div>
                <div class="stat-value">{metrics['overdue']}</div>
                <div class="stat-subtext">⚠️ Milestones past due date</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # 5. Quick Actions & Configurable Rules Toolbar
    action_col1, action_col2, action_col3, action_col4 = st.columns([1.2, 1.2, 1.2, 1.4])

    with action_col1:
        if st.button("✅ Mark All as Read", use_container_width=True, help="Mark all current notifications as read"):
            success, msg = mark_all_notifications_status(is_read=True)
            if success:
                st.success(msg)
                st.rerun()

    with action_col2:
        if st.button("📬 Mark All as Unread", use_container_width=True, help="Mark all notifications as unread"):
            success, msg = mark_all_notifications_status(is_read=False)
            if success:
                st.info(msg)
                st.rerun()

    with action_col3:
        if st.button("🔄 Sync & Refresh", use_container_width=True, help="Scan database for new events and sync notifications"):
            added = sync_system_notifications(
                priority_rules=st.session_state["notif_priority_rules"],
                upcoming_days=st.session_state["upcoming_deadline_days"]
            )
            st.toast(f"Notifications refreshed. {added} new notification(s) found.")
            st.rerun()

    with action_col4:
        if st.button("🧹 Clear Read Alerts", use_container_width=True, help="Remove resolved read notifications"):
            success, msg = clear_all_notifications(read_only=True)
            if success:
                st.success(msg)
                st.rerun()

    # Priority Rules Configuration Expander
    with st.expander("⚙️ Configure Notification Priority Rules & Alert Thresholds", expanded=False):
        st.markdown("""
            <div style="font-size: 0.88rem; color: #475569; margin-bottom: 1rem;">
                Customize how OnboardAI categorizes urgency levels for different onboarding activities.
                Changes take effect on the next notification sync.
            </div>
        """, unsafe_allow_html=True)

        cfg_c1, cfg_c2, cfg_c3 = st.columns(3)
        prio_choices = ["High", "Medium", "Low"]

        with cfg_c1:
            cfg_overdue = st.selectbox(
                "Overdue Checklist Tasks Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("overdue_tasks", "High"))
            )
            cfg_pending_review = st.selectbox(
                "Pending Document Reviews Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("pending_approvals", "High"))
            )
            cfg_rejected = st.selectbox(
                "Rejected Documents Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("rejected_documents", "High"))
            )

        with cfg_c2:
            cfg_upcoming = st.selectbox(
                "Upcoming Deadlines Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("upcoming_deadlines", "Medium"))
            )
            cfg_correction = st.selectbox(
                "Correction Requests Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("correction_requests", "Medium"))
            )
            cfg_days = st.slider(
                "Upcoming Deadline Alert Window (Days)",
                min_value=1,
                max_value=14,
                value=int(st.session_state["upcoming_deadline_days"]),
                help="Notify when a checklist task is due within this many days"
            )

        with cfg_c3:
            cfg_missing_docs = st.selectbox(
                "Missing Document Submissions Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("pending_submissions", "Low"))
            )
            cfg_incomplete = st.selectbox(
                "Incomplete Onboarding Reminders Priority",
                options=prio_choices,
                index=prio_choices.index(st.session_state["notif_priority_rules"].get("incomplete_onboarding", "Low"))
            )

            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Save Priority Rules", type="primary", use_container_width=True):
                st.session_state["notif_priority_rules"] = {
                    "overdue_tasks": cfg_overdue,
                    "pending_approvals": cfg_pending_review,
                    "rejected_documents": cfg_rejected,
                    "upcoming_deadlines": cfg_upcoming,
                    "correction_requests": cfg_correction,
                    "pending_submissions": cfg_missing_docs,
                    "incomplete_onboarding": cfg_incomplete,
                }
                st.session_state["upcoming_deadline_days"] = cfg_days
                sync_system_notifications(
                    priority_rules=st.session_state["notif_priority_rules"],
                    upcoming_days=cfg_days
                )
                st.success("Priority rules updated and alerts re-synchronized!")
                st.rerun()

    st.markdown("<hr style='margin: 1.5rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)

    # 6. Search and Filter Bar
    st.markdown('<h3 class="section-title">🔍 Search & Filter Notifications</h3>', unsafe_allow_html=True)

    f_col1, f_col2, f_col3, f_col4 = st.columns([1.8, 1.2, 1, 1])

    with f_col1:
        search_query = st.text_input(
            "Search Notifications",
            placeholder="Search by candidate name, employee ID, or alert title...",
            label_visibility="collapsed"
        )

    with f_col2:
        category_options = [
            "All Categories",
            "Document Review",
            "Checklist Milestone",
            "Document Submission",
            "General Onboarding"
        ]
        selected_category = st.selectbox(
            "Category Filter",
            options=category_options,
            index=0,
            label_visibility="collapsed"
        )

    with f_col3:
        priority_options = ["All Priorities", "High", "Medium", "Low"]
        selected_priority = st.selectbox(
            "Priority Filter",
            options=priority_options,
            index=0,
            label_visibility="collapsed"
        )

    with f_col4:
        status_options = ["All Notifications", "Unread Only", "Read Only"]
        selected_status_filter = st.selectbox(
            "Status Filter",
            options=status_options,
            index=0,
            label_visibility="collapsed"
        )

    # Map read status filter to parameter
    is_read_param = None
    if selected_status_filter == "Unread Only":
        is_read_param = 0
    elif selected_status_filter == "Read Only":
        is_read_param = 1

    # 7. Fetch Notifications from Database
    notifications = get_all_notifications(
        category=selected_category,
        priority=selected_priority,
        is_read=is_read_param,
        search_term=search_query
    )

    st.markdown(f"""
        <div style="font-size: 0.88rem; color: #64748b; margin-top: -0.3rem; margin-bottom: 1.2rem;">
            Showing <strong>{len(notifications)}</strong> notification{'s' if len(notifications) != 1 else ''} matching criteria.
        </div>
    """, unsafe_allow_html=True)

    # 8. Notification Center Display (Tabs: Interactive Feed & Tabular Overview)
    tab_feed, tab_table = st.tabs(["📋 Notification Feed & Action Triage", "📊 Tabular Overview"])

    # ── TAB 1: NOTIFICATION FEED ──
    with tab_feed:
        if not notifications:
            st.markdown("""
                <div style="background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 3rem; text-align: center; margin: 1rem 0;">
                    <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">🎉</div>
                    <h3 style="margin: 0; color: #1e293b;">All caught up!</h3>
                    <p style="color: #64748b; margin: 0.5rem auto 0 auto; max-width: 400px;">
                        No notifications match the active filter criteria. Check back later or adjust your filters.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            return

        # Render notification cards
        for n in notifications:
            is_unread = n["is_read"] == 0
            border_accent = "#F59E0B" if is_unread else "#E2E8F0"
            bg_card = "#FFFFFF"
            read_badge = '<span style="color: #D97706; font-weight: 700; font-size: 0.8rem;">📬 UNREAD</span>' if is_unread else '<span style="color: #64748B; font-size: 0.8rem;">📭 READ</span>'

            col_card, col_action = st.columns([5, 1.2])

            with col_card:
                st.markdown(f"""
                    <div style="background: {bg_card}; border: 1px solid {border_accent}; border-left: 5px solid {'#F59E0B' if is_unread else '#4F46E5'}; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                {get_priority_badge(n['priority'])}
                                {get_category_badge(n['category'])}
                                {read_badge}
                            </div>
                            <div style="font-size: 0.78rem; color: #64748B;">
                                📅 {str(n['created_at'])[:16]}
                            </div>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 0.2rem;">
                            {n['title']}
                        </div>
                        <div style="font-size: 0.88rem; color: #334155; margin-bottom: 0.5rem; line-height: 1.4;">
                            {n['message']}
                        </div>
                        <div style="font-size: 0.8rem; color: #64748B; display: flex; align-items: center; gap: 0.8rem;">
                            <span>👤 Candidate: <strong>{n['employee_name']}</strong> ({n['employee_code']})</span>
                            <span>🏢 Dept: <strong>{n['department']}</strong></span>
                            <span>📌 Status: <strong>{n['employee_status']}</strong></span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            with col_action:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                btn_key = f"toggle_{n['id']}"
                if is_unread:
                    if st.button("✓ Mark Read", key=btn_key, use_container_width=True):
                        mark_notification_status(n["id"], is_read=True)
                        st.rerun()
                else:
                    if st.button("↩ Mark Unread", key=btn_key, use_container_width=True):
                        mark_notification_status(n["id"], is_read=False)
                        st.rerun()

                del_key = f"del_{n['id']}"
                if st.button("🗑️ Dismiss", key=del_key, use_container_width=True, help="Delete this notification"):
                    delete_notification(n["id"])
                    st.rerun()

            # Optional Context Inspector Expander
            with st.expander(f"🔍 Inspect Context: {n['title']} (#{n['id']})", expanded=False):
                emp_info = get_employee_by_id(n["employee_id"]) if n.get("employee_id") else None
                if emp_info:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"""
                            <strong>Candidate Profile:</strong>
                            <br>• Name: {emp_info['name']}
                            <br>• Employee ID: {emp_info['employee_code']}
                            <br>• Email: {emp_info['email']}
                            <br>• Role: {emp_info['role']}
                            <br>• Department: {emp_info['department']}
                        """, unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                            <strong>Onboarding Status & Context:</strong>
                            <br>• Lifecycle Status: {emp_info['status']}
                            <br>• Start Date: {emp_info['join_date']}
                            <br>• Assigned Manager: {emp_info.get('reporting_manager') or 'N/A'}
                            <br>• Location: {emp_info.get('work_location') or 'HQ'}
                            <br>• Associated Entity: {n.get('reference_type') or 'N/A'} #{n.get('reference_id') or 'N/A'}
                        """, unsafe_allow_html=True)
                else:
                    st.write(f"Reference: {n.get('reference_type') or 'System'} ID #{n.get('reference_id') or 'N/A'}")

                # Quick Navigation Guidance
                ref_type = (n.get("reference_type") or "").lower()
                if "document" in ref_type or "document" in n["category"].lower():
                    st.info("💡 **HR Action:** Navigate to **'Document Review'** in the sidebar to inspect extracted fields and approve or request corrections.")
                elif "task" in ref_type or "checklist" in n["category"].lower():
                    st.info("💡 **HR Action:** Navigate to **'Smart Onboarding Checklist'** in the sidebar to mark this milestone complete or reassign deadlines.")
                else:
                    st.info("💡 **HR Action:** Navigate to **'Employee Management'** or **'Employee Progress Tracking'** to review overall candidate progression.")

    # ── TAB 2: TABULAR OVERVIEW ──
    with tab_table:
        if notifications:
            table_rows = []
            for n in notifications:
                table_rows.append({
                    "Notif ID": f"#{n['id']}",
                    "Priority": n["priority"],
                    "Status": "Unread" if n["is_read"] == 0 else "Read",
                    "Category": n["category"],
                    "Title": n["title"],
                    "Candidate Name": n["employee_name"],
                    "Employee ID": n["employee_code"],
                    "Department": n["department"],
                    "Description": n["message"],
                    "Created Date": str(n["created_at"])[:16]
                })

            df_notifs = pd.DataFrame(table_rows)
            st.dataframe(
                df_notifs,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Priority": st.column_config.TextColumn("Priority", width="small"),
                    "Status": st.column_config.TextColumn("Read Status", width="small"),
                    "Title": st.column_config.TextColumn("Title", width="medium"),
                    "Description": st.column_config.TextColumn("Description", width="large"),
                }
            )
        else:
            st.info("No notification records to display.")
