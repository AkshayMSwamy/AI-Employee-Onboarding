"""
HR Dashboard module for AI-Powered Employee Onboarding System.
Displays welcome section, employee statistics cards, and onboarding status.
"""

import streamlit as st
import pandas as pd
from database.db import get_dashboard_metrics, get_recent_onboardings, get_department_breakdown, get_document_review_metrics


def render_dashboard():
    """Renders the main HR Dashboard view."""
    
    # 1. Welcome Section
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">👋 Welcome back, HR Operations</h1>
            <p class="header-subtitle">
                Monitor employee onboarding pipelines, document review queues, and department readiness in real time.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Key Guardrail Banner
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ System Policy:</strong> AI-assisted document parsing helps extract key information quickly, 
            but all documents and potential discrepancies require <strong>Human HR Review & Approval</strong>. 
            AI extraction does not constitute identity verification.
        </div>
    """, unsafe_allow_html=True)

    # 3. Employee Statistics Cards
    metrics = get_dashboard_metrics()
    review_metrics = get_document_review_metrics()
    pending_reviews = review_metrics.get("pending", metrics.get("pending_docs", 0))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
            <div class="stat-card blue">
                <div class="stat-title">Total Hires</div>
                <div class="stat-value">{metrics['total_employees']}</div>
                <div class="stat-subtext">👥 Total registered new hires</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div class="stat-card amber">
                <div class="stat-title">In Progress</div>
                <div class="stat-value">{metrics['in_progress']}</div>
                <div class="stat-subtext">⏳ Active onboarding journeys</div>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div class="stat-card rose">
                <div class="stat-title">Doc Reviews Needed</div>
                <div class="stat-value">{pending_reviews}</div>
                <div class="stat-subtext">📄 Pending HR verification</div>
            </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
            <div class="stat-card emerald">
                <div class="stat-title">Completed</div>
                <div class="stat-value">{metrics['completed']}</div>
                <div class="stat-subtext">✅ Fully onboarded members</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # 4. Recent Onboarding Pipeline & Department Breakdown
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown('<h3 class="section-title">📋 Recent New Hire Onboardings</h3>', unsafe_allow_html=True)
        recent_hires = get_recent_onboardings(limit=5)

        if recent_hires:
            # Transform to clean DataFrame for display
            df_display = pd.DataFrame([
                {
                    "Code": h["employee_code"],
                    "Employee Name": h["name"],
                    "Department": h["department"],
                    "Role": h["role"],
                    "Start Date": h["join_date"],
                    "Status": h["status"],
                    "Checklist": f"{h['completed_tasks']}/{h['total_tasks']} Done" if h['total_tasks'] > 0 else "Pending"
                }
                for h in recent_hires
            ])
            st.dataframe(
                df_display, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn(
                        "Onboarding Status",
                        help="Current status in the onboarding pipeline"
                    )
                }
            )
        else:
            st.info("No employees registered yet. Go to 'Employee Registration' to add the first new hire.")

    with col_right:
        st.markdown('<h3 class="section-title">🏢 By Department</h3>', unsafe_allow_html=True)
        dept_data = get_department_breakdown()
        
        if dept_data:
            df_dept = pd.DataFrame(dept_data)
            df_dept.rename(columns={"department": "Department", "count": "Hires"}, inplace=True)
            st.dataframe(df_dept, use_container_width=True, hide_index=True)
        else:
            st.write("No department data available.")

        # Quick System Readiness Indicators
        st.markdown('<h3 class="section-title" style="margin-top: 1.5rem;">⚙️ System Status</h3>', unsafe_allow_html=True)
        st.markdown("""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; font-size: 0.88rem; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="margin-bottom: 0.6rem; display: flex; align-items: center; justify-content: space-between;">
                    <span style="color: #475569; font-weight: 500;">Database Engine</span>
                    <span style="background: #ECFDF5; color: #059669; font-weight: 600; font-size: 0.76rem; padding: 0.15rem 0.55rem; border-radius: 9999px; border: 1px solid #A7F3D0;">SQLite Online</span>
                </div>
                <div style="margin-bottom: 0.6rem; display: flex; align-items: center; justify-content: space-between;">
                    <span style="color: #475569; font-weight: 500;">AI Engine</span>
                    <span style="background: #EEF2FF; color: #4F46E5; font-weight: 600; font-size: 0.76rem; padding: 0.15rem 0.55rem; border-radius: 9999px; border: 1px solid #C7D2FE;">Gemma 3 1B</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="color: #475569; font-weight: 500;">Document Parsers</span>
                    <span style="background: #F1F5F9; color: #334155; font-weight: 600; font-size: 0.76rem; padding: 0.15rem 0.55rem; border-radius: 9999px; border: 1px solid #CBD5E1;">PyMuPDF Ready</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
