"""
AI-Powered Employee Onboarding System
Main Application Entrypoint
"""

import os
import streamlit as st
from database.db import init_db, get_unread_notification_count
from modules.dashboard import render_dashboard
from modules.employee_registration import render_employee_registration
from modules.employee_management import render_employee_management
from modules.document_processing import render_document_processing
from modules.document_review import render_document_review
from modules.smart_checklist import render_smart_checklist
from modules.onboarding_progress import render_onboarding_progress
from modules.analytics_reporting import render_analytics_reporting
from modules.notifications import render_notifications


def load_css():
    """Load and inject custom CSS styling."""
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_placeholder_view(feature_name: str, description: str, next_stage_info: str):
    """Renders a clean placeholder for features to be implemented in subsequent stages."""
    st.markdown(f"""
        <div class="header-container">
            <h1 class="header-title">{feature_name}</h1>
            <p class="header-subtitle">{description}</p>
        </div>
        <div class="feature-placeholder">
            <h3>🚧 Stage Ready for Implementation</h3>
            <p>{next_stage_info}</p>
            <div style="display: inline-block; padding: 0.5rem 1rem; background: #e2e8f0; border-radius: 6px; font-weight: 500; font-size: 0.9rem; color: #334155;">
                Current Active Stage: Stage 1 (Foundation & Dashboard)
            </div>
        </div>
    """, unsafe_allow_html=True)


def main():
    # 1. Page Configuration
    st.set_page_config(
        page_title="AI Employee Onboarding System",
        page_icon="🏢",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 2. Database Initialization
    init_db()

    # 3. Load Custom CSS
    load_css()

    # 4. Sidebar Navigation
    with st.sidebar:
        st.markdown("""
            <div class="sidebar-brand-container">
                <div class="sidebar-logo-icon">🏢</div>
                <div>
                    <div class="sidebar-brand-title">OnboardAI</div>
                    <div class="sidebar-brand-tagline">Intelligent Employee Onboarding</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='margin: 0.8rem 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)

        unread_count = get_unread_notification_count()
        if unread_count > 0:
            st.markdown(f"""
                <div class="sidebar-alert-badge">
                    <div class="sidebar-alert-text">
                        <span class="sidebar-alert-dot"></span>
                        <span><strong>{unread_count}</strong> Unread Alert{'s' if unread_count != 1 else ''}</span>
                    </div>
                    <span class="sidebar-alert-action">URGENT</span>
                </div>
            """, unsafe_allow_html=True)

        nav_options = [
            "HR Dashboard",
            "Employee Registration",
            "Employee Management",
            "AI Document Processing",
            "Document Review",
            "Smart Onboarding Checklist",
            "Employee Progress Tracking",
            "Analytics and Reports",
            "Notifications"
        ]

        selected_page = st.radio(
            "Navigation Menu",
            options=nav_options,
            index=0,
            label_visibility="collapsed"
        )

        st.markdown("<hr style='margin: 1.2rem 0 0.8rem 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)

        # Sidebar System Footnote
        st.markdown("""
            <div class="sidebar-system-footer">
                <div style="display: flex; align-items: center; margin-bottom: 0.35rem; font-weight: 600; color: #1E293B;">
                    <span class="status-dot-pulse"></span>
                    <span>System Active & Verified</span>
                </div>
                <div style="color: #64748B; font-size: 0.75rem;">
                    Local AI • Human-in-the-Loop Review
                </div>
            </div>
        """, unsafe_allow_html=True)

    # 5. Route to Selected Feature
    if selected_page == "HR Dashboard":
        render_dashboard()
    elif selected_page == "Employee Registration":
        render_employee_registration()
    elif selected_page == "Employee Management":
        render_employee_management()
    elif selected_page == "AI Document Processing":
        render_document_processing()
    elif selected_page == "Document Review":
        render_document_review()
    elif selected_page == "Smart Onboarding Checklist":
        render_smart_checklist()
    elif selected_page == "Employee Progress Tracking":
        render_onboarding_progress()
    elif selected_page == "Analytics and Reports":
        render_analytics_reporting()
    elif selected_page == "Notifications":
        render_notifications()


if __name__ == "__main__":
    main()
