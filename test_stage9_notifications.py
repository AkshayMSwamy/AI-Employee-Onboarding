"""
Comprehensive test suite for Stage 9: Notifications & Reminders
Tests:
1. No notifications (empty or cleared table)
2. Pending document review alert generation
3. Rejected document alert generation
4. Correction request alert generation
5. Overdue checklist task alert generation
6. Upcoming checklist deadline alert generation
7. Duplicate notification prevention (deduplication)
8. Mark read and unread functionality (individual & bulk)
9. Invalid / orphaned employee ID handling
10. Empty database scenario handling
"""

import sqlite3
from datetime import datetime, timedelta

from database.db import (
    get_connection,
    init_db,
    sync_system_notifications,
    get_all_notifications,
    get_notification_metrics,
    get_unread_notification_count,
    mark_notification_status,
    mark_all_notifications_status,
    delete_notification,
    clear_all_notifications,
    DEFAULT_NOTIFICATION_PRIORITIES
)

def run_tests():
    print("=" * 60)
    print("RUNNING STAGE 9 NOTIFICATIONS & REMINDERS TEST SUITE")
    print("=" * 60)

    # Initialize db
    init_db()

    # ── Test 1: Sync & Deduplication Test ──
    # First sync
    added_1 = sync_system_notifications()
    print(f"[TEST 1] First sync inserted: {added_1} notifications.")
    
    # Second sync immediately following
    added_2 = sync_system_notifications()
    print(f"[TEST 1.1] Second sync inserted (deduplication check): {added_2} notifications.")
    assert added_2 == 0, f"Deduplication failed! Expected 0 duplicates, got {added_2}"
    print("  -> PASSED: Duplicate notification prevention verified.")

    # ── Test 2: Notification Center Metrics ──
    metrics = get_notification_metrics()
    unread_cnt = get_unread_notification_count()
    print(f"[TEST 2] Metrics: Total={metrics['total']}, Unread={metrics['unread']}, HighPrio={metrics['high_priority']}, Overdue={metrics['overdue']}")
    assert metrics["total"] > 0, "Expected non-zero total notifications"
    assert metrics["unread"] == unread_cnt, "Unread count mismatch between metrics and count helper"
    print("  -> PASSED: Notification metrics calculated accurately.")

    # ── Test 3: Notification Categories & Types Verification ──
    all_notifs = get_all_notifications()
    categories_present = set(n["category"] for n in all_notifs)
    print(f"[TEST 3] Categories present: {categories_present}")
    
    has_doc_review = any(n["category"] == "Document Review" for n in all_notifs)
    has_milestone = any(n["category"] == "Checklist Milestone" for n in all_notifs)
    print(f"  Document Review alerts found: {has_doc_review}")
    print(f"  Checklist Milestone alerts found: {has_milestone}")
    assert has_doc_review, "Expected Document Review notifications"
    assert has_milestone, "Expected Checklist Milestone notifications"
    print("  -> PASSED: Expected notification types generated.")

    # ── Test 4: Pending Document Review Alert ──
    pending_doc_notifs = [n for n in all_notifs if "Awaiting Review" in n["title"]]
    print(f"[TEST 4] Pending document review notifications count: {len(pending_doc_notifs)}")
    assert len(pending_doc_notifs) > 0, "Expected at least 1 pending document review alert"
    assert pending_doc_notifs[0]["priority"] == "High", f"Expected High priority, got {pending_doc_notifs[0]['priority']}"
    print("  -> PASSED: Pending document review alert generated with High priority.")

    # ── Test 5: Overdue Checklist Task Alert ──
    overdue_notifs = [n for n in all_notifs if "Overdue Milestone" in n["title"]]
    print(f"[TEST 5] Overdue milestone notifications count: {len(overdue_notifs)}")
    assert len(overdue_notifs) > 0, "Expected at least 1 overdue task alert"
    assert overdue_notifs[0]["priority"] == "High"
    print("  -> PASSED: Overdue checklist task alert generated with High priority.")

    # ── Test 6: Rejected Document & Correction Request Alerts ──
    # Create test document records with 'Rejected' and 'Correction Requested'
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM employees LIMIT 1")
    test_emp_id = c.fetchone()["id"]

    # Insert temporary rejected document
    c.execute("""
        INSERT INTO documents (employee_id, document_type, file_name, verification_status, discrepancy_notes)
        VALUES (?, 'Test Certification', 'cert_fail.pdf', 'Rejected', 'Document expired in 2024')
    """, (test_emp_id,))
    rej_doc_id = c.lastrowid

    # Insert temporary correction requested document
    c.execute("""
        INSERT INTO documents (employee_id, document_type, file_name, verification_status, discrepancy_notes)
        VALUES (?, 'Address Proof', 'utility_bill.pdf', 'Correction Requested', 'Utility bill is older than 90 days')
    """, (test_emp_id,))
    corr_doc_id = c.lastrowid

    # Insert upcoming task
    upcoming_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    c.execute("""
        INSERT INTO checklist_tasks (employee_id, task_title, category, is_completed, due_date)
        VALUES (?, 'Upcoming Compliance Signing', 'Compliance', 0, ?)
    """, (test_emp_id, upcoming_date))
    up_task_id = c.lastrowid
    conn.commit()
    conn.close()

    # Sync notifications to detect newly inserted items
    sync_system_notifications(upcoming_days=7)
    updated_notifs = get_all_notifications()

    # Verify Rejected Document alert
    rej_alerts = [n for n in updated_notifs if n["reference_id"] == rej_doc_id and "Rejected" in n["title"]]
    print(f"[TEST 6.1] Rejected document alert: {len(rej_alerts)} found.")
    assert len(rej_alerts) == 1, "Expected exactly 1 rejected document notification"
    assert rej_alerts[0]["priority"] == "High"
    assert "Document expired in 2024" in rej_alerts[0]["message"]
    print("  -> PASSED: Rejected document alert created with discrepancy feedback.")

    # Verify Correction Requested alert
    corr_alerts = [n for n in updated_notifs if n["reference_id"] == corr_doc_id and "Correction Requested" in n["title"]]
    print(f"[TEST 6.2] Correction requested alert: {len(corr_alerts)} found.")
    assert len(corr_alerts) == 1, "Expected exactly 1 correction request notification"
    assert corr_alerts[0]["priority"] == "Medium"
    print("  -> PASSED: Correction request alert created with Medium priority.")

    # Verify Upcoming Deadline alert
    up_alerts = [n for n in updated_notifs if n["reference_id"] == up_task_id and "Upcoming Deadline" in n["title"]]
    print(f"[TEST 6.3] Upcoming task alert: {len(up_alerts)} found.")
    assert len(up_alerts) == 1, "Expected exactly 1 upcoming task deadline notification"
    assert up_alerts[0]["priority"] == "Medium"
    print("  -> PASSED: Upcoming checklist deadline alert created.")

    # ── Test 7: Mark Read / Unread Actions ──
    target_notif_id = rej_alerts[0]["id"]
    # Mark as read
    s1, m1 = mark_notification_status(target_notif_id, is_read=True)
    assert s1
    chk1 = get_all_notifications(search_term="Test Certification")
    assert chk1[0]["is_read"] == 1, "Notification failed to mark as read"
    print(f"[TEST 7.1] Notification #{target_notif_id} marked as read.")

    # Mark as unread
    s2, m2 = mark_notification_status(target_notif_id, is_read=False)
    assert s2
    chk2 = get_all_notifications(search_term="Test Certification")
    assert chk2[0]["is_read"] == 0, "Notification failed to mark as unread"
    print(f"[TEST 7.2] Notification #{target_notif_id} marked back as unread.")

    # Bulk mark all read
    s3, m3 = mark_all_notifications_status(is_read=True)
    assert s3
    assert get_unread_notification_count() == 0, "Expected 0 unread after bulk mark read"
    print(f"[TEST 7.3] Bulk mark all read: {m3}")

    # Bulk mark all unread
    s4, m4 = mark_all_notifications_status(is_read=False)
    assert s4
    assert get_unread_notification_count() > 0, "Expected unread notifications after bulk unread"
    print(f"[TEST 7.4] Bulk mark all unread: {m4}")
    print("  -> PASSED: Individual and bulk read/unread state changes verified.")

    # ── Test 8: Filter & Search Functionality ──
    # Search by candidate name
    srch_notifs = get_all_notifications(search_term="Sarah")
    assert len(srch_notifs) > 0
    for sn in srch_notifs:
        assert "sarah" in sn["employee_name"].lower() or "sarah" in sn["message"].lower() or "sarah" in sn["title"].lower()

    # Filter by Priority
    high_notifs = get_all_notifications(priority="High")
    assert len(high_notifs) > 0
    for hn in high_notifs:
        assert hn["priority"] == "High"

    # Filter by Category
    chk_cat_notifs = get_all_notifications(category="Checklist Milestone")
    assert len(chk_cat_notifs) > 0
    for cn in chk_cat_notifs:
        assert cn["category"] == "Checklist Milestone"

    print("  -> PASSED: Search, priority filtering, and category filtering verified.")

    # ── Test 9: Invalid / Orphaned Employee ID Handling ──
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (employee_id, title, message, category, priority, is_read, dedup_key)
        VALUES (999999, 'Orphaned Alert', 'System task alert for deleted profile', 'General Onboarding', 'Low', 0, 'orphan_test_key')
    """)
    orphan_id = c.lastrowid
    conn.commit()
    conn.close()

    orphan_results = get_all_notifications(search_term="Orphaned Alert")
    assert len(orphan_results) == 1
    # Check that LEFT JOIN handled missing employee gracefully without throwing NULL error
    assert orphan_results[0]["employee_name"] == "System / Unassigned"
    print(f"[TEST 9] Orphaned employee ID handled gracefully: employee_name='{orphan_results[0]['employee_name']}'")
    delete_notification(orphan_id)
    print("  -> PASSED: Invalid/orphaned employee IDs handled safely.")

    # Clean up test rows
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM documents WHERE id IN (?, ?)", (rej_doc_id, corr_doc_id))
    c.execute("DELETE FROM checklist_tasks WHERE id = ?", (up_task_id,))
    c.execute("DELETE FROM notifications WHERE id IN (?, ?)", (rej_alerts[0]["id"], corr_alerts[0]["id"]))
    conn.commit()
    conn.close()

    # ── Test 10: Empty Notifications State ──
    # Test clearing all notifications
    clear_all_notifications(read_only=False)
    empty_notifs = get_all_notifications()
    empty_metrics = get_notification_metrics()
    assert len(empty_notifs) == 0
    assert empty_metrics["total"] == 0
    assert empty_metrics["unread"] == 0
    print("[TEST 10] Cleared notifications state verified: total=0, unread=0")

    # Restore notifications via sync
    restored = sync_system_notifications()
    assert restored > 0
    print(f"[TEST 10.1] Restored {restored} notifications via system sync.")
    print("  -> PASSED: Empty state and recovery sync verified.")

    print("=" * 60)
    print("ALL 10 STAGE 9 TEST CASES PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
