"""
Employee Registration module for AI-Powered Employee Onboarding System.
Provides a streamlined intake form for registering new employees with validation,
automatic ID generation, duplicate prevention, and onboarding task initialization.
"""

import re
from datetime import date
import streamlit as st
import pandas as pd
from config import REPORTING_MANAGERS
from database.db import (
    register_new_employee,
    check_email_exists,
    generate_next_employee_code,
    get_recent_onboardings
)


def validate_email_format(email: str) -> bool:
    """Validates standard email address syntax."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


def render_employee_registration():
    """Renders the Employee Registration interface."""
    
    # 1. Page Header
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">👤 Employee Registration</h1>
            <p class="header-subtitle">
                Register new hires to create their workforce profile, generate a unique employee ID, 
                and provision default onboarding compliance checklists.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # 2. Informational Banner & Compliance Guardrail
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ Compliance & Onboarding Policy:</strong> All registered new hires will be automatically assigned
            standard onboarding compliance milestones. Documents submitted during later onboarding stages will be analyzed 
            by local AI (Gemma 3 1B) but strictly require <strong>Human HR approval</strong>. AI extraction does not verify identity.
        </div>
    """, unsafe_allow_html=True)

    # 3. Next Employee ID Preview
    next_code = generate_next_employee_code()
    
    st.markdown(f"""
        <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 0.9rem 1.2rem; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);">
            <div>
                <span style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;">Assigned System Identifier</span>
                <div style="font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-top: 0.15rem;">Next Available Employee ID: <span style="color: #4F46E5;">{next_code}</span></div>
            </div>
            <div style="background: #EEF2FF; color: #4F46E5; font-weight: 600; font-size: 0.85rem; padding: 0.4rem 0.8rem; border-radius: 6px; border: 1px solid #C7D2FE;">
                ⚡ Auto-Generated
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4. Registration Form
    with st.form("employee_registration_form", clear_on_submit=False):
        st.markdown('<h3 class="section-title" style="margin-top: 0; margin-bottom: 1rem;">Candidate Profile Details</h3>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 👤 Personal & Contact Info")
            
            full_name = st.text_input(
                "Full Name *",
                placeholder="e.g. Alexander Vance",
                help="Legal full name of the new hire"
            )

            email = st.text_input(
                "Work / Primary Email *",
                placeholder="e.g. alexander.vance@company.com",
                help="Must be a valid and unique email address"
            )

            phone = st.text_input(
                "Phone Number *",
                placeholder="e.g. +1 (555) 234-5678",
                help="Direct contact phone number"
            )

            work_location = st.selectbox(
                "Work Location *",
                options=[
                    "San Francisco, CA (HQ)",
                    "New York, NY",
                    "Austin, TX",
                    "London, UK",
                    "Remote - US",
                    "Remote - International",
                    "Other"
                ],
                help="Designated primary work station or remote status"
            )

        with col2:
            st.markdown("##### 🏢 Role & Department Info")

            department = st.selectbox(
                "Department *",
                options=[
                    "Engineering",
                    "Product",
                    "Design",
                    "Analytics",
                    "Human Resources",
                    "Finance & Legal",
                    "Marketing",
                    "Sales",
                    "Operations"
                ],
                help="Assigned business division"
            )

            job_role = st.text_input(
                "Job Role *",
                placeholder="e.g. Senior Frontend Engineer",
                help="Official position title"
            )

            reporting_manager = st.selectbox(
                "Reporting Manager *",
                options=REPORTING_MANAGERS,
                help="Select assigned direct supervisor"
            )

            join_date = st.date_input(
                "Joining Date *",
                value=date.today(),
                help="Official first day of employment"
            )

        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

        # Form Submission Button
        submitted = st.form_submit_button(
            "🚀 Register Employee & Initialize Onboarding",
            use_container_width=True,
            type="primary"
        )

    # 5. Form Processing & Validation
    if submitted:
        # Validate required fields
        errors = []
        if not full_name.strip():
            errors.append("• Full Name is required.")
        if not email.strip():
            errors.append("• Work Email is required.")
        elif not validate_email_format(email.strip()):
            errors.append("• Work Email format is invalid (e.g. name@company.com).")
        elif check_email_exists(email.strip()):
            errors.append(f"• Duplicate Registration: An employee with email '{email.strip()}' is already registered.")

        if not phone.strip():
            errors.append("• Phone Number is required.")
        elif len(re.sub(r'[^0-9]', '', phone.strip())) < 7:
            errors.append("• Phone Number must contain at least 7 digits.")

        if not job_role.strip():
            errors.append("• Job Role is required.")
        if not reporting_manager.strip():
            errors.append("• Reporting Manager is required.")

        if errors:
            st.error("### ⚠️ Please correct the following errors:\n" + "\n".join(errors))
        else:
            # Prepare data payload
            employee_payload = {
                "name": full_name.strip(),
                "email": email.strip().lower(),
                "phone": phone.strip(),
                "department": department,
                "role": job_role.strip(),
                "join_date": str(join_date),
                "reporting_manager": reporting_manager.strip(),
                "work_location": work_location,
                "status": "In Progress"
            }

            # Register in database
            success, message, new_record = register_new_employee(employee_payload)

            if success:
                st.session_state["last_registered"] = new_record
                st.rerun()
            else:
                st.error(f"❌ Failed to register employee: {message}")

    # 6. Display Success Feedback Banner if an employee was just registered
    if "last_registered" in st.session_state:
        reg = st.session_state["last_registered"]
        st.markdown(f"""
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; border-radius: 10px; padding: 1.5rem; margin-top: 1.5rem; margin-bottom: 2rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem;">
                    <div style="font-size: 1.2rem; font-weight: 700; color: #166534;">
                        🎉 Employee Successfully Registered!
                    </div>
                    <span style="background: #dcfce7; color: #15803d; font-weight: 700; font-size: 0.9rem; padding: 0.3rem 0.8rem; border-radius: 9999px;">
                        {reg.get('employee_code')}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; font-size: 0.9rem; color: #1e293b;">
                    <div><strong>Full Name:</strong> {reg.get('name')}</div>
                    <div><strong>Email:</strong> {reg.get('email')}</div>
                    <div><strong>Department:</strong> {reg.get('department')}</div>
                    <div><strong>Job Role:</strong> {reg.get('role')}</div>
                    <div><strong>Location:</strong> {reg.get('work_location')}</div>
                    <div><strong>Reporting Manager:</strong> {reg.get('reporting_manager')}</div>
                    <div><strong>Joining Date:</strong> {reg.get('join_date')}</div>
                    <div><strong>Onboarding Status:</strong> <span style="color: #d97706; font-weight: 600;">{reg.get('status')}</span></div>
                </div>
                <div style="margin-top: 1rem; font-size: 0.85rem; color: #15803d; border-top: 1px dashed #bbf7d0; padding-top: 0.8rem;">
                    ✅ 6 standard onboarding checklist tasks provisioned and profile added to the live HR Dashboard pipeline.
                </div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("➕ Register Another Employee", type="secondary"):
            del st.session_state["last_registered"]
            st.rerun()

    # 7. Recent Registrations Live Roster
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">📋 Recently Registered Employees</h3>', unsafe_allow_html=True)
    st.markdown("<p style='font-size: 0.88rem; color: #64748b; margin-top: -0.5rem; margin-bottom: 1rem;'>Live database snapshot showing newly onboarded team members.</p>", unsafe_allow_html=True)

    recent_hires = get_recent_onboardings(limit=8)
    if recent_hires:
        df_recent = pd.DataFrame([
            {
                "ID": h["employee_code"],
                "Full Name": h["name"],
                "Email": h["email"],
                "Department": h["department"],
                "Role": h["role"],
                "Location": h.get("work_location") or "HQ",
                "Manager": h.get("reporting_manager") or "N/A",
                "Start Date": h["join_date"],
                "Status": h["status"]
            }
            for h in recent_hires
        ])

        st.dataframe(
            df_recent,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No registered employees found in the database.")
