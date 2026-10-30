"""
Database compatibility bridge.
Re-exports database functionality from database.db to maintain backwards compatibility.
"""
from database.db import (
    get_connection,
    init_db,
    seed_sample_data,
    generate_next_employee_code,
    check_email_exists,
    register_new_employee,
    get_dashboard_metrics,
    get_recent_onboardings,
    get_department_breakdown,
    get_all_employees,
    get_employee_by_id,
    get_employee_by_code,
    get_employee_tasks,
    get_employee_documents,
    update_employee,
    update_employee_status,
    delete_employee,
    get_all_departments,
    get_all_statuses,
    save_uploaded_document,
    get_documents_by_employee,
    get_document_by_id,
    update_document_review,
    get_all_documents_with_employee_info,
    get_document_review_metrics,
    get_review_queue_documents,
    submit_hr_document_decision,
    get_document_audit_trail,
    get_all_audit_logs,
    # Stage 6: Smart Checklist functions
    get_checklist_summary_all_employees,
    add_checklist_task,
    toggle_checklist_task,
    delete_checklist_task,
    get_task_categories,
    # Stage 7: Onboarding Progress Tracking functions
    get_progress_overview_metrics,
    get_all_employees_progress,
    get_employee_progress_detail,
    get_employee_timeline,
    get_overdue_checklist_tasks,
    # Stage 8: Analytics & Reporting functions
    get_min_max_join_dates,
    get_analytics_filtered_data,
    # Stage 9: Notifications & Reminders functions
    sync_system_notifications,
    get_all_notifications,
    get_notification_metrics,
    get_unread_notification_count,
    mark_notification_status,
    mark_all_notifications_status,
    delete_notification,
    clear_all_notifications,
    DEFAULT_NOTIFICATION_PRIORITIES,
    DB_PATH
)

# Compatibility alias for earlier prototype naming
def get_dashboard_stats():
    """Alias for get_dashboard_metrics for compatibility."""
    return get_dashboard_metrics()

def get_recent_employees(limit=5):
    """Alias for get_recent_onboardings for compatibility."""
    return get_recent_onboardings(limit=limit)

