"""
Styling module providing professional UI styling and components for Streamlit.
"""
import streamlit as st

def apply_custom_styles():
    """Injects custom CSS to style the HR Onboarding application professionally."""
    st.markdown("""
        <style>
        /* Import clean modern typography */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        /* Main Container Padding */
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 1300px;
        }

        /* Header Welcome Banner */
        .welcome-banner {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #312e81 100%);
            border-radius: 16px;
            padding: 2rem 2.2rem;
            color: #ffffff;
            margin-bottom: 1.8rem;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.08);
            position: relative;
            overflow: hidden;
        }

        .welcome-banner::after {
            content: "";
            position: absolute;
            top: -50px;
            right: -50px;
            width: 200px;
            height: 200px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, rgba(99, 102, 241, 0) 70%);
            border-radius: 50%;
            pointer-events: none;
        }

        .welcome-title {
            font-size: 1.85rem;
            font-weight: 700;
            color: #ffffff !important;
            margin-bottom: 0.4rem;
            letter-spacing: -0.02em;
        }

        .welcome-subtitle {
            font-size: 0.98rem;
            color: #94a3b8;
            margin-bottom: 0;
            line-height: 1.5;
        }

        /* Statistics Card Styling */
        .stat-card {
            background: #ffffff;
            border-radius: 14px;
            padding: 1.35rem 1.25rem;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
            transition: all 0.2s ease-in-out;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -3px rgba(0, 0, 0, 0.08);
            border-color: #cbd5e1;
        }

        .stat-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.75rem;
        }

        .stat-icon {
            width: 42px;
            height: 42px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }

        .icon-blue { background-color: #eff6ff; color: #2563eb; }
        .icon-amber { background-color: #fffbeb; color: #d97706; }
        .icon-purple { background-color: #faf5ff; color: #7c3aed; }
        .icon-emerald { background-color: #ecfdf5; color: #059669; }

        .stat-label {
            font-size: 0.82rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
        }

        .stat-value {
            font-size: 2.1rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.1;
            margin-bottom: 0.4rem;
        }

        .stat-footer {
            font-size: 0.8rem;
            color: #64748b;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        /* Quick Action & Section Cards */
        .section-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
        }

        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.2rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .section-desc {
            font-size: 0.88rem;
            color: #64748b;
            margin-bottom: 1.2rem;
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 0.25rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-align: center;
        }

        .badge-success { background-color: #dcfce7; color: #15803d; }
        .badge-warning { background-color: #fef3c7; color: #b45309; }
        .badge-info { background-color: #e0f2fe; color: #0369a1; }
        .badge-neutral { background-color: #f1f5f9; color: #475569; }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }

        .sidebar-brand {
            padding: 1rem 0.5rem 1.5rem 0.5rem;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 1.2rem;
        }

        .brand-title {
            font-size: 1.35rem;
            font-weight: 800;
            color: #0f172a;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .brand-subtitle {
            font-size: 0.78rem;
            color: #64748b;
            margin-top: 0.2rem;
        }

        .sidebar-footer {
            margin-top: 2rem;
            padding: 1rem;
            background: #f1f5f9;
            border-radius: 10px;
            font-size: 0.78rem;
            color: #64748b;
            line-height: 1.4;
        }

        /* Coming soon card */
        .upcoming-stage-card {
            background: #ffffff;
            border: 2px dashed #cbd5e1;
            border-radius: 16px;
            padding: 3rem 2rem;
            text-align: center;
            margin-top: 1rem;
        }

        .upcoming-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }

        .upcoming-title {
            font-size: 1.4rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }

        .upcoming-desc {
            font-size: 0.95rem;
            color: #64748b;
            max-width: 600px;
            margin: 0 auto 1.5rem auto;
            line-height: 1.5;
        }
        </style>
    """, unsafe_allow_html=True)
