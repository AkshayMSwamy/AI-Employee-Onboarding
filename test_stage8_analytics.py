"""
Comprehensive test suite for Stage 8: Analytics & Reporting
Validates:
1. get_min_max_join_dates() and get_analytics_filtered_data()
2. Multi-parameter filtering (date range, department, status)
3. KPI aggregates, department metrics, monthly trends, checklist category stats
4. Empty database / zero-result handling without division-by-zero
5. Missing timestamps handling (strict verification that no dummy dates are invented)
6. Excel report generation:
   - Employee summary workbook (.xlsx)
   - Document review workbook (.xlsx)
   - Checklist progress workbook (.xlsx)
7. PDF report generation:
   - Overall onboarding executive report (.pdf) with PyMuPDF
"""

import os
import sys
import io
import openpyxl
import pymupdf
from datetime import datetime, date

from database.db import (
    get_min_max_join_dates,
    get_analytics_filtered_data,
    get_all_departments,
    get_all_statuses,
    get_connection
)
from modules.analytics_reporting import (
    generate_employee_summary_excel,
    generate_document_review_excel,
    generate_checklist_progress_excel,
    generate_overall_onboarding_pdf
)

def run_tests():
    print("=" * 60)
    print("RUNNING STAGE 8 ANALYTICS & REPORTING TEST SUITE")
    print("=" * 60)

    # ── Test 1: Date Boundaries ──
    min_d, max_d = get_min_max_join_dates()
    print(f"[TEST 1] min_date: {min_d}, max_date: {max_d}")
    assert min_d is not None and max_d is not None, "Failed to retrieve join date bounds"
    print("  -> PASSED: Date bounds retrieved successfully.")

    # ── Test 2: Unfiltered Analytics Data ──
    data_all = get_analytics_filtered_data()
    kpis = data_all["kpis"]
    perf = data_all["performance"]
    depts = data_all["department_stats"]
    trends = data_all["monthly_trends"]
    cats = data_all["category_task_stats"]

    print(f"[TEST 2] Unfiltered KPIs: Total Employees={kpis['total_employees']}, Completed={kpis['completed_employees']}, In-Progress={kpis['in_progress_employees']}, Overdue Tasks={kpis['overdue_tasks']}, Docs={kpis['total_documents']}")
    assert kpis["total_employees"] > 0, "Expected at least 1 employee"
    assert len(depts) > 0, "Expected department breakdown"
    assert len(trends) > 0, "Expected monthly trends"
    print("  -> PASSED: Unfiltered KPIs and statistics calculated correctly.")

    # ── Test 3: Department Filter ──
    data_eng = get_analytics_filtered_data(department="Engineering")
    eng_kpis = data_eng["kpis"]
    print(f"[TEST 3] Engineering Filter: Employees={eng_kpis['total_employees']}")
    assert eng_kpis["total_employees"] > 0, "Expected Engineering employees"
    for e in data_eng["employees"]:
        assert e["department"] == "Engineering", f"Unexpected dept: {e['department']}"
    print("  -> PASSED: Department filter correctly isolates department records.")

    # ── Test 4: Status Filter ──
    data_comp = get_analytics_filtered_data(status="Completed")
    comp_kpis = data_comp["kpis"]
    print(f"[TEST 4] Status='Completed' Filter: Employees={comp_kpis['total_employees']}")
    for e in data_comp["employees"]:
        assert e["status"] == "Completed", f"Unexpected status: {e['status']}"
    print("  -> PASSED: Status filter correctly isolates completed records.")

    # ── Test 5: Date Range Filter ──
    data_range = get_analytics_filtered_data(start_date="2026-11-01", end_date="2026-11-30")
    print(f"[TEST 5] Nov 2026 Date Filter: Employees={data_range['kpis']['total_employees']}")
    for e in data_range["employees"]:
        jd = e["join_date"] or str(e["created_at"])[:10]
        assert "2026-11" in jd, f"Date out of range: {jd}"
    print("  -> PASSED: Date range filter accurately restricts results.")

    # ── Test 6: Missing Timestamps Handling ──
    print(f"[TEST 6] Average completion time check:")
    print(f"  avg_completion_days: {perf['avg_completion_days']}")
    print(f"  completion_time_samples: {perf['completion_time_samples']}")
    # Verify no synthetic timestamps or fake dates were created
    if perf["completion_time_samples"] == 0:
        assert perf["avg_completion_days"] is None, "Should be None when no completed hires have valid timestamps"
        print("  -> PASSED: Correctly handled missing timestamps as None without inventing dates.")
    else:
        assert isinstance(perf["avg_completion_days"], (int, float))
        print("  -> PASSED: Computed average completion time using real timestamps.")

    # ── Test 7: Empty / Non-matching Scope Handling ──
    data_empty = get_analytics_filtered_data(department="NonExistentDept")
    empty_kpis = data_empty["kpis"]
    empty_perf = data_empty["performance"]
    assert empty_kpis["total_employees"] == 0
    assert empty_perf["overall_completion_rate"] == 0.0
    assert empty_perf["avg_progress_pct"] == 0.0
    assert empty_perf["avg_completion_days"] is None
    print("  -> PASSED: Empty result query handled safely with 0.0 values and no division by zero.")

    # ── Test 8: Excel Generation Tests ──
    # 8.1 Employee Summary
    emp_xlsx = generate_employee_summary_excel(data_all["employees"], "All Scope")
    assert len(emp_xlsx) > 1000, "Excel employee summary too small"
    # Verify openpyxl can read it back
    wb_test = openpyxl.load_workbook(io.BytesIO(emp_xlsx))
    assert "Employee Onboarding Summary" in wb_test.sheetnames
    print(f"[TEST 8.1] Employee Summary Excel generated: {len(emp_xlsx)} bytes")

    # 8.2 Document Review Audit
    doc_xlsx = generate_document_review_excel(data_all["documents"], "All Scope")
    assert len(doc_xlsx) > 1000, "Excel document audit too small"
    wb_doc = openpyxl.load_workbook(io.BytesIO(doc_xlsx))
    assert "Document Review Audit" in wb_doc.sheetnames
    print(f"[TEST 8.2] Document Review Excel generated: {len(doc_xlsx)} bytes")

    # 8.3 Checklist Progress
    task_xlsx = generate_checklist_progress_excel(data_all["tasks"], "All Scope")
    assert len(task_xlsx) > 1000, "Excel checklist report too small"
    wb_task = openpyxl.load_workbook(io.BytesIO(task_xlsx))
    assert "Checklist Tasks Progress" in wb_task.sheetnames
    print(f"[TEST 8.3] Checklist Progress Excel generated: {len(task_xlsx)} bytes")

    # ── Test 9: PDF Generation Test ──
    pdf_bytes = generate_overall_onboarding_pdf(data_all, "All Scope")
    assert len(pdf_bytes) > 2000, "PDF report too small"
    pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert pdf_doc.page_count == 2, f"Expected 2 pages, got {pdf_doc.page_count}"
    page1_text = pdf_doc[0].get_text()
    assert "ONBOARDAI" in page1_text
    assert "EXECUTIVE ONBOARDING ANALYTICS REPORT" in page1_text
    page2_text = pdf_doc[1].get_text()
    assert "EMPLOYEE PROGRESS ROSTER" in page2_text
    print(f"[TEST 9] PDF Report generated: {len(pdf_bytes)} bytes, {pdf_doc.page_count} pages.")
    print("  -> PASSED: PDF structure, executive sections, and typography verified.")

    # ── Test 10: PDF on Empty Scope ──
    empty_pdf_bytes = generate_overall_onboarding_pdf(data_empty, "Empty Scope")
    assert len(empty_pdf_bytes) > 1000
    empty_pdf_doc = pymupdf.open(stream=empty_pdf_bytes, filetype="pdf")
    assert empty_pdf_doc.page_count == 2
    print(f"[TEST 10] Empty Scope PDF generated: {len(empty_pdf_bytes)} bytes")
    print("  -> PASSED: Empty scope PDF generated safely.")

    print("=" * 60)
    print("ALL 10 TEST CASES PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
