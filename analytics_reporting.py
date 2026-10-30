"""
Analytics and Reporting module for OnboardAI (Stage 8).
Provides HR administrators with comprehensive workforce onboarding analytics,
interactive Plotly visualizations, performance analysis metrics, flexible multi-parameter
filtering, and downloadable reports in Excel (.xlsx) and PDF (.pdf) formats.
"""

import io
import os
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pymupdf

from database.db import (
    get_analytics_filtered_data,
    get_min_max_join_dates,
    get_all_departments,
    get_all_statuses
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXCEL REPORT GENERATORS (openpyxl)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_excel_header_styling(ws, title: str, subtitle: str, filters_summary: str, num_cols: int):
    """Applies clean executive styling to Excel sheet headers."""
    # Palette definition
    navy_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    sub_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    
    title_font = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
    meta_font = Font(name="Segoe UI", size=9, italic=True, color="475569")
    
    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    cell_title = ws.cell(row=1, column=1, value=title)
    cell_title.fill = navy_fill
    cell_title.font = title_font
    cell_title.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # Subtitle / Generation time
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cell_meta = ws.cell(row=2, column=1, value=f"{subtitle}  |  Generated on: {now_str}")
    cell_meta.fill = sub_fill
    cell_meta.font = meta_font
    cell_meta.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # Filters applied
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=num_cols)
    cell_filters = ws.cell(row=3, column=1, value=f"Applied Filter Scope: {filters_summary}")
    cell_filters.fill = sub_fill
    cell_filters.font = meta_font
    cell_filters.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 20

    # Empty spacer row
    ws.row_dimensions[4].height = 10


def _style_data_table(ws, start_row: int, headers: List[str], data_rows: List[List[Any]]):
    """Styles table header and zebra-striped rows with thin borders and auto column width."""
    tbl_header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    tbl_header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    
    zebra_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    zebra_odd = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    
    cell_font = Font(name="Segoe UI", size=10, color="0F172A")
    thin_border_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    # Write Table Headers
    ws.row_dimensions[start_row].height = 24
    for col_idx, h_text in enumerate(headers, start=1):
        c = ws.cell(row=start_row, column=col_idx, value=h_text)
        c.fill = tbl_header_fill
        c.font = tbl_header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border

    # Write Data Rows
    current_row = start_row + 1
    for r_idx, row_values in enumerate(data_rows):
        ws.row_dimensions[current_row].height = 20
        fill_to_use = zebra_odd if r_idx % 2 == 1 else zebra_even
        
        for col_idx, val in enumerate(row_values, start=1):
            c = ws.cell(row=current_row, column=col_idx, value=val)
            c.fill = fill_to_use
            c.font = cell_font
            c.border = cell_border
            
            # Smart alignment based on content type
            if isinstance(val, (int, float)):
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif isinstance(val, str) and (val.endswith("%") or len(val) <= 12 and "-" in val):
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")
                
        current_row += 1

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip merged banner rows
            if cell.row < start_row:
                continue
            if cell.value:
                val_str = str(cell.value)
                max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)


def generate_employee_summary_excel(employees: List[Dict[str, Any]], filters_info: str) -> bytes:
    """Generates an executive-ready Excel workbook summarizing employee onboarding progress."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employee Onboarding Summary"

    headers = [
        "Employee Code", "Full Name", "Email Address", "Department", "Role",
        "Work Location", "Joining Date", "Status", "Progress %",
        "Total Tasks", "Completed Tasks", "Pending Tasks", "Overdue Tasks",
        "Total Docs", "Approved Docs", "Pending Docs", "Rejected Docs"
    ]

    data_rows = []
    for e in employees:
        data_rows.append([
            e.get("employee_code") or "—",
            e.get("name") or "—",
            e.get("email") or "—",
            e.get("department") or "—",
            e.get("role") or "—",
            e.get("work_location") or "HQ",
            e.get("join_date") or "—",
            e.get("status") or "In Progress",
            f"{e.get('progress_pct', 0)}%",
            e.get("total_tasks", 0),
            e.get("completed_tasks", 0),
            e.get("pending_tasks", 0),
            e.get("overdue_tasks", 0),
            e.get("total_docs", 0),
            e.get("approved_docs", 0),
            e.get("pending_docs", 0),
            e.get("rejected_docs", 0)
        ])

    _apply_excel_header_styling(
        ws,
        title="ONBOARDAI — EMPLOYEE ONBOARDING PROGRESS REPORT",
        subtitle="Workforce Onboarding Lifecycle & Milestone Completion Audit",
        filters_summary=filters_info,
        num_cols=len(headers)
    )
    _style_data_table(ws, start_row=5, headers=headers, data_rows=data_rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_document_review_excel(documents: List[Dict[str, Any]], filters_info: str) -> bytes:
    """Generates an Excel workbook auditing document compliance and HR reviews."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Document Review Audit"

    headers = [
        "Doc ID", "Employee Code", "Candidate Name", "Department", "Document Type",
        "Filename", "File Format", "Upload Date", "AI Extraction Status",
        "HR Review Status", "Reviewed By", "Reviewed Date", "Discrepancy & Audit Notes"
    ]

    data_rows = []
    for d in documents:
        data_rows.append([
            f"#{d.get('id')}",
            d.get("employee_code") or "—",
            d.get("employee_name") or "—",
            d.get("department") or "—",
            d.get("document_type") or "—",
            d.get("file_name") or "—",
            d.get("file_type") or "DOC",
            str(d.get("created_at") or "")[:19],
            d.get("ai_status") or "Completed",
            d.get("verification_status") or "Pending HR Review",
            d.get("reviewed_by") or "—",
            str(d.get("reviewed_at") or "—")[:19],
            d.get("discrepancy_notes") or "None"
        ])

    _apply_excel_header_styling(
        ws,
        title="ONBOARDAI — DOCUMENT COMPLIANCE & REVIEW AUDIT REPORT",
        subtitle="Human-in-the-Loop Document Verification Status & Discrepancy Log",
        filters_summary=filters_info,
        num_cols=len(headers)
    )
    _style_data_table(ws, start_row=5, headers=headers, data_rows=data_rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_checklist_progress_excel(tasks: List[Dict[str, Any]], filters_info: str) -> bytes:
    """Generates an Excel workbook auditing onboarding checklist tasks."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Checklist Tasks Progress"

    headers = [
        "Task ID", "Employee Code", "Candidate Name", "Department",
        "Milestone Task Title", "Category", "Status", "Due Date",
        "Completed At", "Overdue Status"
    ]

    data_rows = []
    for t in tasks:
        is_comp = t.get("is_completed", 0) == 1
        status_label = "Completed" if is_comp else "Pending"
        overdue_label = "YES (OVERDUE)" if t.get("is_overdue") else "NO"
        
        data_rows.append([
            f"#{t.get('id')}",
            t.get("employee_code") or "—",
            t.get("employee_name") or "—",
            t.get("department") or "—",
            t.get("task_title") or "—",
            t.get("category") or "General",
            status_label,
            t.get("due_date") or "—",
            str(t.get("completed_at") or "—")[:19],
            overdue_label
        ])

    _apply_excel_header_styling(
        ws,
        title="ONBOARDAI — ONBOARDING CHECKLIST MILESTONES REPORT",
        subtitle="Departmental Tasks, Compliance Requirements & SLA Tracking",
        filters_summary=filters_info,
        num_cols=len(headers)
    )
    _style_data_table(ws, start_row=5, headers=headers, data_rows=data_rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 2. PDF REPORT GENERATOR (PyMuPDF)
# ─────────────────────────────────────────────────────────────────────────────

def generate_overall_onboarding_pdf(data: Dict[str, Any], filters_info: str) -> bytes:
    """
    Generates a structured, professional executive PDF report summarizing workforce onboarding,
    department statistics, document compliance, and overdue task escalations.
    """
    doc = pymupdf.open()
    kpis = data["kpis"]
    perf = data["performance"]
    depts = data["department_stats"]
    emps = data["employees"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── PAGE 1: Executive KPI Dashboard & Department Breakdown ──
    page1 = doc.new_page(width=595, height=842) # A4 portrait

    # Header Banner Box
    page1.draw_rect(pymupdf.Rect(35, 30, 560, 92), color=(0.12, 0.16, 0.23), fill=(0.12, 0.16, 0.23))
    page1.insert_text((50, 54), "ONBOARDAI  |  EXECUTIVE ONBOARDING ANALYTICS REPORT", color=(1, 1, 1), fontsize=13, fontname="helv", fontfile=None)
    page1.insert_text((50, 70), "AI-Powered Employee Onboarding System • Workforce Intelligence & Compliance", color=(0.7, 0.78, 0.9), fontsize=8.5)
    page1.insert_text((50, 83), f"Report Generated: {now_str}  |  Filters: {filters_info}", color=(0.85, 0.85, 0.85), fontsize=8)

    # Section 1: Executive KPI Summary Box
    page1.draw_rect(pymupdf.Rect(35, 104, 560, 196), color=(0.88, 0.91, 0.94), fill=(0.97, 0.98, 0.99))
    page1.insert_text((50, 120), "1. EXECUTIVE WORKFORCE METRICS", color=(0.12, 0.16, 0.23), fontsize=10, fontname="helv")

    # Metric Grid in 2 rows
    # Row 1: Employees & Overdue
    m_y1 = 142
    page1.insert_text((50, m_y1), "Total Employees:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((150, m_y1), str(kpis["total_employees"]), color=(0.08, 0.1, 0.15), fontsize=10, fontname="helv")

    page1.insert_text((195, m_y1), "Completed:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((275, m_y1), f"{kpis['completed_employees']} ({perf['overall_completion_rate']}%)", color=(0.06, 0.6, 0.35), fontsize=10, fontname="helv")

    page1.insert_text((345, m_y1), "In-Progress:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((425, m_y1), str(kpis["in_progress_employees"]), color=(0.85, 0.55, 0.05), fontsize=10, fontname="helv")

    page1.insert_text((480, m_y1), "Overdue Tasks:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((545, m_y1), str(kpis["overdue_tasks"]), color=(0.85, 0.2, 0.3), fontsize=10, fontname="helv")

    # Row 2: Document Verification
    m_y2 = 168
    page1.insert_text((50, m_y2), "Total Documents:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((150, m_y2), str(kpis["total_documents"]), color=(0.08, 0.1, 0.15), fontsize=10, fontname="helv")

    page1.insert_text((195, m_y2), "Approved Docs:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((275, m_y2), str(kpis["approved_documents"]), color=(0.06, 0.6, 0.35), fontsize=10, fontname="helv")

    page1.insert_text((345, m_y2), "Pending Review:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((425, m_y2), str(kpis["pending_documents"]), color=(0.85, 0.55, 0.05), fontsize=10, fontname="helv")

    page1.insert_text((480, m_y2), "Rejected Docs:", color=(0.4, 0.45, 0.5), fontsize=8.5)
    page1.insert_text((545, m_y2), str(kpis["rejected_documents"]), color=(0.85, 0.2, 0.3), fontsize=10, fontname="helv")

    # Row 3: SLA / Performance Timing
    m_y3 = 186
    avg_days_text = f"{perf['avg_completion_days']} days (based on {perf['completion_time_samples']} completed hires)" if perf["avg_completion_days"] is not None else "N/A — Insufficient completion timestamps"
    page1.insert_text((50, m_y3), f"Average Completion Time: {avg_days_text}", color=(0.3, 0.35, 0.4), fontsize=8)

    # Section 2: Department-wise Onboarding Table
    sec2_y = 212
    page1.insert_text((50, sec2_y), "2. DEPARTMENT ONBOARDING PERFORMANCE BREAKDOWN", color=(0.12, 0.16, 0.23), fontsize=10, fontname="helv")

    # Table Header
    tbl_y = 224
    page1.draw_rect(pymupdf.Rect(35, tbl_y, 560, tbl_y + 18), color=(0.15, 0.39, 0.92), fill=(0.15, 0.39, 0.92))
    page1.insert_text((45, tbl_y + 12), "Department", color=(1, 1, 1), fontsize=8.5, fontname="helv")
    page1.insert_text((190, tbl_y + 12), "Total Hires", color=(1, 1, 1), fontsize=8.5, fontname="helv")
    page1.insert_text((270, tbl_y + 12), "Completed", color=(1, 1, 1), fontsize=8.5, fontname="helv")
    page1.insert_text((350, tbl_y + 12), "In Progress", color=(1, 1, 1), fontsize=8.5, fontname="helv")
    page1.insert_text((430, tbl_y + 12), "Completion Rate", color=(1, 1, 1), fontsize=8.5, fontname="helv")
    page1.insert_text((510, tbl_y + 12), "Overdue Tasks", color=(1, 1, 1), fontsize=8.5, fontname="helv")

    row_y = tbl_y + 18
    if depts:
        for idx, d_stat in enumerate(depts):
            bg_color = (0.97, 0.98, 0.99) if idx % 2 == 1 else (1, 1, 1)
            page1.draw_rect(pymupdf.Rect(35, row_y, 560, row_y + 17), color=(0.88, 0.91, 0.94), fill=bg_color)
            page1.insert_text((45, row_y + 12), str(d_stat["department"])[:22], color=(0.1, 0.15, 0.2), fontsize=8)
            page1.insert_text((205, row_y + 12), str(d_stat["total_employees"]), color=(0.1, 0.15, 0.2), fontsize=8)
            page1.insert_text((285, row_y + 12), str(d_stat["completed"]), color=(0.06, 0.6, 0.35), fontsize=8)
            page1.insert_text((365, row_y + 12), str(d_stat["in_progress"]), color=(0.85, 0.55, 0.05), fontsize=8)
            page1.insert_text((445, row_y + 12), f"{d_stat['completion_rate_pct']}%", color=(0.1, 0.15, 0.2), fontsize=8)
            page1.insert_text((530, row_y + 12), str(d_stat["overdue_tasks"]), color=(0.85, 0.2, 0.3) if d_stat["overdue_tasks"] > 0 else (0.1, 0.15, 0.2), fontsize=8)
            row_y += 17
    else:
        page1.draw_rect(pymupdf.Rect(35, row_y, 560, row_y + 20), color=(0.88, 0.91, 0.94), fill=(1, 1, 1))
        page1.insert_text((45, row_y + 14), "No department records match the current filter criteria.", color=(0.5, 0.5, 0.5), fontsize=8)
        row_y += 20

    # Section 3: Compliance & Document Status Overview
    sec3_y = row_y + 20
    page1.insert_text((50, sec3_y), "3. COMPLIANCE AUDIT & AI-VERIFICATION SUMMARY", color=(0.12, 0.16, 0.23), fontsize=10, fontname="helv")

    page1.draw_rect(pymupdf.Rect(35, sec3_y + 10, 560, sec3_y + 90), color=(0.88, 0.91, 0.94), fill=(0.98, 0.99, 1.0))
    page1.insert_text((50, sec3_y + 28), f"• Document Approval Rate: {perf['doc_approval_rate']}% of reviewed documents approved.", color=(0.15, 0.2, 0.25), fontsize=8.5)
    page1.insert_text((50, sec3_y + 44), f"• Document Rejection Rate: {perf['doc_rejection_rate']}% failed compliance check or required re-upload.", color=(0.15, 0.2, 0.25), fontsize=8.5)
    page1.insert_text((50, sec3_y + 60), f"• Checklist Tasks Completion Rate: {perf['task_completion_rate']}% of assigned milestones completed.", color=(0.15, 0.2, 0.25), fontsize=8.5)
    page1.insert_text((50, sec3_y + 76), "• Human-in-the-Loop Mandate: All extractions require Human HR verification before granting compliance.", color=(0.35, 0.4, 0.45), fontsize=8)

    # Footer Page 1
    page1.insert_text((45, 815), "CONFIDENTIAL • Generated by OnboardAI (Human-in-the-Loop HR Intelligence) • Page 1 of 2", color=(0.5, 0.55, 0.6), fontsize=7.5)

    # ── PAGE 2: Candidate Roster & Escalation Action Items ──
    page2 = doc.new_page(width=595, height=842)

    # Header Page 2
    page2.draw_rect(pymupdf.Rect(35, 30, 560, 68), color=(0.12, 0.16, 0.23), fill=(0.12, 0.16, 0.23))
    page2.insert_text((50, 50), "ONBOARDAI  |  EMPLOYEE PROGRESS ROSTER & ESCALATIONS", color=(1, 1, 1), fontsize=12, fontname="helv")
    page2.insert_text((50, 64), f"Workforce Progress Tracking Roster  |  Audit Timestamp: {now_str}", color=(0.7, 0.78, 0.9), fontsize=8)

    # Employee Table
    r_y = 85
    page2.insert_text((50, r_y), "4. WORKFORCE PROGRESS ROSTER (FILTERED SCOPE)", color=(0.12, 0.16, 0.23), fontsize=10, fontname="helv")

    p2_tbl_y = r_y + 12
    page2.draw_rect(pymupdf.Rect(35, p2_tbl_y, 560, p2_tbl_y + 18), color=(0.15, 0.39, 0.92), fill=(0.15, 0.39, 0.92))
    page2.insert_text((45, p2_tbl_y + 12), "Code", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((115, p2_tbl_y + 12), "Employee Name", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((230, p2_tbl_y + 12), "Department", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((330, p2_tbl_y + 12), "Joining Date", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((400, p2_tbl_y + 12), "Status", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((475, p2_tbl_y + 12), "Progress", color=(1, 1, 1), fontsize=8, fontname="helv")
    page2.insert_text((520, p2_tbl_y + 12), "Overdue", color=(1, 1, 1), fontsize=8, fontname="helv")

    p2_row_y = p2_tbl_y + 18
    # Display up to 25 employees on page 2
    if emps:
        for idx, emp in enumerate(emps[:25]):
            bg_color = (0.97, 0.98, 0.99) if idx % 2 == 1 else (1, 1, 1)
            page2.draw_rect(pymupdf.Rect(35, p2_row_y, 560, p2_row_y + 16), color=(0.88, 0.91, 0.94), fill=bg_color)
            page2.insert_text((45, p2_row_y + 11), str(emp.get("employee_code") or "—"), color=(0.1, 0.15, 0.2), fontsize=7.5)
            page2.insert_text((115, p2_row_y + 11), str(emp.get("name") or "—")[:20], color=(0.1, 0.15, 0.2), fontsize=7.5)
            page2.insert_text((230, p2_row_y + 11), str(emp.get("department") or "—")[:18], color=(0.1, 0.15, 0.2), fontsize=7.5)
            page2.insert_text((330, p2_row_y + 11), str(emp.get("join_date") or "—"), color=(0.1, 0.15, 0.2), fontsize=7.5)
            page2.insert_text((400, p2_row_y + 11), str(emp.get("status") or "In Progress")[:12], color=(0.1, 0.15, 0.2), fontsize=7.5)
            page2.insert_text((480, p2_row_y + 11), f"{emp.get('progress_pct', 0)}%", color=(0.15, 0.39, 0.92), fontsize=7.5, fontname="helv")
            od_cnt = emp.get("overdue_tasks", 0)
            page2.insert_text((530, p2_row_y + 11), str(od_cnt), color=(0.85, 0.2, 0.3) if od_cnt > 0 else (0.1, 0.15, 0.2), fontsize=7.5)
            p2_row_y += 16
    else:
        page2.draw_rect(pymupdf.Rect(35, p2_row_y, 560, p2_row_y + 20), color=(0.88, 0.91, 0.94), fill=(1, 1, 1))
        page2.insert_text((45, p2_row_y + 14), "No employee records found matching current criteria.", color=(0.5, 0.5, 0.5), fontsize=8)
        p2_row_y += 20

    # Overdue Task Action Escalation Box
    esc_y = min(p2_row_y + 20, 710)
    page2.draw_rect(pymupdf.Rect(35, esc_y, 560, esc_y + 80), color=(0.95, 0.75, 0.75), fill=(0.99, 0.96, 0.96))
    page2.insert_text((50, esc_y + 20), "⚠️ HR ESCALATION & SLA NOTICE:", color=(0.7, 0.1, 0.2), fontsize=9, fontname="helv")
    page2.insert_text((50, esc_y + 36), f"• Total Overdue Checklist Milestones: {kpis['overdue_tasks']} across {kpis['employees_with_overdue']} employee(s).", color=(0.2, 0.2, 0.2), fontsize=8.5)
    page2.insert_text((50, esc_y + 52), f"• Documents Awaiting Verification: {kpis['pending_documents']} document(s) currently require Human HR approval.", color=(0.2, 0.2, 0.2), fontsize=8.5)
    page2.insert_text((50, esc_y + 68), "• Required Action: Review overdue tasks with assigned managers and clear pending document verification queues.", color=(0.35, 0.35, 0.35), fontsize=8)

    # Footer Page 2
    page2.insert_text((45, 815), "CONFIDENTIAL • Generated by OnboardAI (Human-in-the-Loop HR Intelligence) • Page 2 of 2", color=(0.5, 0.55, 0.6), fontsize=7.5)

    return doc.tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# 3. STREAMLIT UI RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_analytics_reporting():
    """Renders the comprehensive HR Analytics and Reporting module."""
    
    # ── Page Header ──
    st.markdown("""
        <div class="header-container">
            <h1 class="header-title">📊 Analytics & Reporting</h1>
            <p class="header-subtitle">
                Workforce onboarding intelligence, compliance verification rates, department throughput,
                SLA bottlenecks, and audit-ready Excel & PDF exports.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # ── Compliance Policy Callout ──
    st.markdown("""
        <div class="info-callout">
            <strong>🛡️ Data Integrity & Verification Standard:</strong> All metrics and reports reflect verified
            database records in real time. Historical completion times strictly use recorded timestamps without
            synthetic estimates.
        </div>
    """, unsafe_allow_html=True)

    # ── 1. Filtering Controls ──
    st.markdown('<h3 class="section-title">🔍 Analytics Scope & Filters</h3>', unsafe_allow_html=True)
    
    min_date_str, max_date_str = get_min_max_join_dates()
    today_dt = date.today()
    default_start = date.fromisoformat(min_date_str) if min_date_str else today_dt
    default_end = date.fromisoformat(max_date_str) if max_date_str else today_dt
    
    # Ensure start is not after end
    if default_start > default_end:
        default_start, default_end = default_end, default_start

    col_f1, col_f2, col_f3 = st.columns([2, 1.2, 1.2])

    with col_f1:
        date_selection = st.date_input(
            "Filter by Joining Date Range",
            value=(default_start, default_end),
            help="Filter employees whose joining/registration date falls within this calendar window"
        )

    # Parse date range safely to handle Streamlit intermediate single-click state
    start_filter_str = None
    end_filter_str = None
    if isinstance(date_selection, (tuple, list)):
        if len(date_selection) >= 1 and date_selection[0]:
            start_filter_str = str(date_selection[0])
        if len(date_selection) >= 2 and date_selection[1]:
            end_filter_str = str(date_selection[1])
        elif len(date_selection) == 1 and date_selection[0]:
            end_filter_str = str(date_selection[0])

    with col_f2:
        dept_options = ["All Departments"] + get_all_departments()
        selected_dept = st.selectbox(
            "Department Filter",
            options=dept_options,
            index=0,
            help="Filter analytics to a specific business division"
        )

    with col_f3:
        status_options = ["All Statuses"] + get_all_statuses()
        selected_status = st.selectbox(
            "Employee Status Filter",
            options=status_options,
            index=0,
            help="Filter by candidate onboarding lifecycle status"
        )

    # Human-readable filter summary for reports
    filter_desc_parts = []
    if start_filter_str and end_filter_str:
        filter_desc_parts.append(f"Joining Window: {start_filter_str} to {end_filter_str}")
    if selected_dept != "All Departments":
        filter_desc_parts.append(f"Dept: {selected_dept}")
    else:
        filter_desc_parts.append("All Departments")
    if selected_status != "All Statuses":
        filter_desc_parts.append(f"Status: {selected_status}")
    else:
        filter_desc_parts.append("All Statuses")
    filters_info_str = " | ".join(filter_desc_parts)

    st.markdown(f"""
        <div style="font-size: 0.84rem; color: #64748b; margin-top: -0.3rem; margin-bottom: 1.5rem;">
            Active Scope: <strong>{filters_info_str}</strong>
        </div>
    """, unsafe_allow_html=True)

    # ── Fetch Filtered Analytics Data ──
    data = get_analytics_filtered_data(
        start_date=start_filter_str,
        end_date=end_filter_str,
        department=selected_dept,
        status=selected_status
    )
    kpis = data["kpis"]
    perf = data["performance"]
    employees = data["employees"]
    documents = data["documents"]
    tasks = data["tasks"]
    dept_stats = data["department_stats"]
    monthly_trends = data["monthly_trends"]
    cat_stats = data["category_task_stats"]

    # ── 2. Dashboard Analytics (KPI Metric Cards) ──
    st.markdown('<h3 class="section-title">📈 Core Workforce KPI Metrics</h3>', unsafe_allow_html=True)

    # Row 1: 4 Cards
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        st.markdown(f"""
            <div class="stat-card blue">
                <div class="stat-title">Total Employees</div>
                <div class="stat-value">{kpis['total_employees']}</div>
                <div class="stat-subtext">👥 Matching active filters</div>
            </div>
        """, unsafe_allow_html=True)

    with col_m2:
        st.markdown(f"""
            <div class="stat-card emerald">
                <div class="stat-title">Completed Onboardings</div>
                <div class="stat-value">{kpis['completed_employees']}</div>
                <div class="stat-subtext">✅ Fully verified & complete</div>
            </div>
        """, unsafe_allow_html=True)

    with col_m3:
        st.markdown(f"""
            <div class="stat-card amber">
                <div class="stat-title">In-Progress Onboardings</div>
                <div class="stat-value">{kpis['in_progress_employees']}</div>
                <div class="stat-subtext">⏳ Active onboarding pipelines</div>
            </div>
        """, unsafe_allow_html=True)

    with col_m4:
        st.markdown(f"""
            <div class="stat-card rose">
                <div class="stat-title">Overdue Tasks</div>
                <div class="stat-value">{kpis['overdue_tasks']}</div>
                <div class="stat-subtext">⚠️ Milestones past due date</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 0.8rem;'></div>", unsafe_allow_html=True)

    # Row 2: 3 Cards for Document Compliance
    col_m5, col_m6, col_m7 = st.columns(3)

    with col_m5:
        st.markdown(f"""
            <div class="stat-card amber">
                <div class="stat-title">Pending Doc Reviews</div>
                <div class="stat-value">{kpis['pending_documents']}</div>
                <div class="stat-subtext">⏳ Awaiting human verification</div>
            </div>
        """, unsafe_allow_html=True)

    with col_m6:
        st.markdown(f"""
            <div class="stat-card emerald">
                <div class="stat-title">Approved Documents</div>
                <div class="stat-value">{kpis['approved_documents']}</div>
                <div class="stat-subtext">🛡️ Verified by HR Operations</div>
            </div>
        """, unsafe_allow_html=True)

    with col_m7:
        st.markdown(f"""
            <div class="stat-card rose">
                <div class="stat-title">Rejected Documents</div>
                <div class="stat-value">{kpis['rejected_documents']}</div>
                <div class="stat-subtext">❌ Failed compliance checks</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # ── Empty Filter State Check ──
    if kpis["total_employees"] == 0:
        st.warning("⚠️ No workforce records match the selected date range, department, or status filters. Please broaden your criteria.")
        return

    # ── 3. Visualizations ──
    st.markdown('<h3 class="section-title">📊 Visual Analytics & Performance Trends</h3>', unsafe_allow_html=True)

    # Visualizations Row 1: Status Distribution & Department Progress
    col_v1, col_v2 = st.columns(2)

    with col_v1:
        st.markdown("##### 📌 Completed vs. In-Progress Onboarding Breakdown")
        status_labels = ["Completed", "In Progress"]
        status_counts = [kpis["completed_employees"], kpis["in_progress_employees"]]
        status_colors = ["#10B981", "#3B82F6"]

        if kpis["pending_status_employees"] > 0:
            status_labels.append("Other Status")
            status_counts.append(kpis["pending_status_employees"])
            status_colors.append("#F59E0B")

        fig_status = go.Figure(data=[go.Pie(
            labels=status_labels,
            values=status_counts,
            hole=0.45,
            marker=dict(colors=status_colors),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>"
        )])
        fig_status.update_layout(
            margin=dict(t=20, b=20, l=10, r=10),
            height=300,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with col_v2:
        st.markdown("##### 🏢 Department-Wise Onboarding Status")
        if dept_stats:
            dept_names = [d["department"] for d in dept_stats]
            dept_completed = [d["completed"] for d in dept_stats]
            dept_inprogress = [d["in_progress"] for d in dept_stats]

            fig_dept = go.Figure(data=[
                go.Bar(name="Completed", x=dept_names, y=dept_completed, marker_color="#10B981"),
                go.Bar(name="In Progress", x=dept_names, y=dept_inprogress, marker_color="#3B82F6")
            ])
            fig_dept.update_layout(
                barmode="group",
                margin=dict(t=20, b=40, l=10, r=10),
                height=300,
                xaxis_title="Department",
                yaxis_title="Employees",
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_dept, use_container_width=True)
        else:
            st.info("No department data available for current selection.")

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # Visualizations Row 2: Document Approval Status & Checklist Completion
    col_v3, col_v4 = st.columns(2)

    with col_v3:
        st.markdown("##### 📑 Document Verification Status Distribution")
        doc_labels = ["Approved", "Pending HR Review", "Rejected", "Correction Needed"]
        doc_values = [
            kpis["approved_documents"],
            kpis["pending_documents"],
            kpis["rejected_documents"],
            kpis["correction_documents"]
        ]
        doc_colors = ["#10B981", "#F59E0B", "#EF4444", "#3B82F6"]

        # Filter out 0 categories if no documents
        active_doc_items = [(l, v, c) for l, v, c in zip(doc_labels, doc_values, doc_colors) if v > 0]
        if active_doc_items:
            fig_docs = go.Figure(data=[go.Pie(
                labels=[x[0] for x in active_doc_items],
                values=[x[1] for x in active_doc_items],
                hole=0.45,
                marker=dict(colors=[x[2] for x in active_doc_items]),
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>Documents: %{value}<extra></extra>"
            )])
            fig_docs.update_layout(
                margin=dict(t=20, b=20, l=10, r=10),
                height=300,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_docs, use_container_width=True)
        else:
            st.info("No documents uploaded in the selected scope.")

    with col_v4:
        st.markdown("##### ✅ Checklist Completion by Category")
        if cat_stats:
            cat_names = [c["category"] for c in cat_stats]
            cat_done = [c["completed"] for c in cat_stats]
            cat_pending = [c["pending"] for c in cat_stats]
            cat_overdue = [c["overdue"] for c in cat_stats]

            fig_cat = go.Figure(data=[
                go.Bar(name="Completed", x=cat_names, y=cat_done, marker_color="#10B981"),
                go.Bar(name="Pending", x=cat_names, y=cat_pending, marker_color="#94A3B8"),
                go.Bar(name="Overdue", x=cat_names, y=cat_overdue, marker_color="#EF4444")
            ])
            fig_cat.update_layout(
                barmode="stack",
                margin=dict(t=20, b=40, l=10, r=10),
                height=300,
                xaxis_title="Category",
                yaxis_title="Checklist Tasks",
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No checklist task data available.")

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # Visualization Row 3: Monthly Employee Onboarding Trends
    st.markdown("##### 📅 Monthly Employee Onboarding Intake Trends")
    if monthly_trends:
        trend_df = pd.DataFrame(monthly_trends)
        fig_trend = px.bar(
            trend_df,
            x="month",
            y="new_hires",
            text="new_hires",
            labels={"month": "Month (YYYY-MM)", "new_hires": "New Hires Joined"},
            color_discrete_sequence=["#4F46E5"]
        )
        fig_trend.update_traces(textposition="outside")
        fig_trend.update_layout(
            margin=dict(t=20, b=30, l=10, r=10),
            height=280,
            xaxis=dict(type="category")
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No chronological monthly data available for the active filters.")

    st.markdown("<hr style='margin: 2.5rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)

    # ── 4. Performance Analysis Section ──
    st.markdown('<h3 class="section-title">⚡ Deep-Dive Performance Analysis</h3>', unsafe_allow_html=True)

    perf_col1, perf_col2, perf_col3 = st.columns(3)

    with perf_col1:
        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; height: 100%;">
                <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase;">Overall Completion Rate</div>
                <div style="font-size: 2rem; font-weight: 700; color: #10B981; margin: 0.3rem 0;">{perf['overall_completion_rate']}%</div>
                <div style="font-size: 0.82rem; color: #334155;">
                    <strong>{kpis['completed_employees']}</strong> of {kpis['total_employees']} hires fully onboarded.
                    <br>Average progress score: <strong>{perf['avg_progress_pct']}%</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with perf_col2:
        if perf["avg_completion_days"] is not None:
            time_display = f"{perf['avg_completion_days']} <span style='font-size: 1.1rem; font-weight: 500;'>days</span>"
            time_note = f"Based on {perf['completion_time_samples']} completed employee(s) with recorded completion timestamps."
        else:
            time_display = "<span style='font-size: 1.25rem; color: #64748B;'>N/A — Timestamps Pending</span>"
            time_note = "Requires completion timestamps recorded when checklist tasks and reviews are finalized."

        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; height: 100%;">
                <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase;">Avg. Onboarding Turnaround</div>
                <div style="font-size: 2rem; font-weight: 700; color: #4F46E5; margin: 0.3rem 0;">{time_display}</div>
                <div style="font-size: 0.82rem; color: #334155;">{time_note}</div>
            </div>
        """, unsafe_allow_html=True)

    with perf_col3:
        st.markdown(f"""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.2rem; height: 100%;">
                <div style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase;">Compliance & Verification SLA</div>
                <div style="font-size: 2rem; font-weight: 700; color: #0F172A; margin: 0.3rem 0;">
                    {perf['doc_approval_rate']}% <span style="font-size: 0.9rem; font-weight: 500; color: #64748B;">approved</span>
                </div>
                <div style="font-size: 0.82rem; color: #334155;">
                    Rejection Rate: <strong>{perf['doc_rejection_rate']}%</strong>
                    <br>Task Milestone Completion: <strong>{perf['task_completion_rate']}%</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # Department-wise Completion Rates Table
    st.markdown("##### 🏢 Department-Wise Completion & SLA Metrics")
    if dept_stats:
        dept_table_data = []
        for d in dept_stats:
            dept_table_data.append({
                "Department": d["department"],
                "Total Hires": d["total_employees"],
                "Completed": d["completed"],
                "In Progress": d["in_progress"],
                "Completion Rate": f"{d['completion_rate_pct']}%",
                "Avg Progress": f"{d['avg_progress_pct']}%",
                "Overdue Tasks": d["overdue_tasks"]
            })
        st.dataframe(pd.DataFrame(dept_table_data), use_container_width=True, hide_index=True)

    # Overdue Tasks Inspection (if any)
    if kpis["overdue_tasks"] > 0:
        st.markdown("##### ⚠️ Overdue Checklist Tasks Escalation Queue")
        overdue_tasks_list = [t for t in tasks if t.get("is_overdue")]
        if overdue_tasks_list:
            od_df_data = []
            for ot in overdue_tasks_list:
                od_df_data.append({
                    "Task ID": f"#{ot['id']}",
                    "Candidate": f"{ot['employee_name']} ({ot['employee_code']})",
                    "Department": ot["department"],
                    "Task Title": ot["task_title"],
                    "Category": ot["category"],
                    "Due Date": ot["due_date"],
                    "Status": "⚠️ Overdue"
                })
            st.dataframe(pd.DataFrame(od_df_data), use_container_width=True, hide_index=True)

    st.markdown("<hr style='margin: 2.5rem 0; border: none; border-top: 1px solid #e2e8f0;' />", unsafe_allow_html=True)

    # ── 5. Report Generation & Exports ──
    st.markdown('<h3 class="section-title">📥 Executive Report Downloads & Data Export</h3>', unsafe_allow_html=True)
    st.markdown("""
        <p style="font-size: 0.92rem; color: #64748b; margin-top: -0.5rem; margin-bottom: 1.5rem;">
            Export audit-ready reports reflecting the filtered scope. All downloads are generated dynamically
            from the SQLite database with verified timestamps.
        </p>
    """, unsafe_allow_html=True)

    rep_col1, rep_col2, rep_col3, rep_col4 = st.columns(4)

    # Report 1: Employee Summary (Excel)
    with rep_col1:
        st.markdown("""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="font-size: 1.3rem;">📊</div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A; margin-top: 0.3rem;">Employee Summary</div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 0.2rem;">Complete workforce roster, progress %, and milestones.</div>
                </div>
                <div style="font-size: 0.75rem; color: #4F46E5; font-weight: 600;">Format: Excel (.xlsx)</div>
            </div>
        """, unsafe_allow_html=True)
        excel_emp_bytes = generate_employee_summary_excel(employees, filters_info_str)
        st.download_button(
            label="📥 Download Excel",
            data=excel_emp_bytes,
            file_name=f"OnboardAI_Employee_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_emp_excel"
        )

    # Report 2: Document Review Report (Excel)
    with rep_col2:
        st.markdown("""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="font-size: 1.3rem;">📑</div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A; margin-top: 0.3rem;">Document Audit</div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 0.2rem;">AI extractions, human review decisions, and audit notes.</div>
                </div>
                <div style="font-size: 0.75rem; color: #4F46E5; font-weight: 600;">Format: Excel (.xlsx)</div>
            </div>
        """, unsafe_allow_html=True)
        excel_doc_bytes = generate_document_review_excel(documents, filters_info_str)
        st.download_button(
            label="📥 Download Excel",
            data=excel_doc_bytes,
            file_name=f"OnboardAI_Document_Audit_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_doc_excel"
        )

    # Report 3: Checklist Progress Report (Excel)
    with rep_col3:
        st.markdown("""
            <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 1.1rem; height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="font-size: 1.3rem;">✅</div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A; margin-top: 0.3rem;">Checklist Tasks</div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-top: 0.2rem;">Detailed task milestones, completion dates, and overdue SLA flags.</div>
                </div>
                <div style="font-size: 0.75rem; color: #4F46E5; font-weight: 600;">Format: Excel (.xlsx)</div>
            </div>
        """, unsafe_allow_html=True)
        excel_task_bytes = generate_checklist_progress_excel(tasks, filters_info_str)
        st.download_button(
            label="📥 Download Excel",
            data=excel_task_bytes,
            file_name=f"OnboardAI_Checklist_Progress_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_task_excel"
        )

    # Report 4: Overall Executive Onboarding Report (PDF)
    with rep_col4:
        st.markdown("""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.1rem; height: 180px; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <div style="font-size: 1.3rem;">📄</div>
                    <div style="font-weight: 700; font-size: 0.95rem; color: #1e293b; margin-top: 0.3rem;">Executive PDF Report</div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.2rem;">Multi-page summary with KPI cards, department SLA, and roster.</div>
                </div>
                <div style="font-size: 0.75rem; color: #dc2626; font-weight: 600;">Format: Adobe PDF (.pdf)</div>
            </div>
        """, unsafe_allow_html=True)
        pdf_report_bytes = generate_overall_onboarding_pdf(data, filters_info_str)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_report_bytes,
            file_name=f"OnboardAI_Executive_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="dl_pdf_report"
        )
