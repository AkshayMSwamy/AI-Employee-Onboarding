"""
Database helper module for AI-Powered Employee Onboarding System.
Handles SQLite connection, schema creation, employee registrations, and dashboard data queries.
"""

import sqlite3
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from utils.auth_security import (
    hash_password,
    verify_password,
    validate_password_strength,
    require_role,
    require_employee_access,
    check_role,
    PermissionDeniedError
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "onboarding.db")


def get_connection():
    """Establish and return a SQLite database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables and seed initial demo data if empty."""
    conn = get_connection()
    cursor = conn.cursor()

    # Employees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            join_date TEXT NOT NULL,
            reporting_manager TEXT,
            work_location TEXT,
            status TEXT DEFAULT 'In Progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Ensure reporting_manager and work_location columns exist in older schemas
    cursor.execute("PRAGMA table_info(employees)")
    existing_columns = [row["name"] for row in cursor.fetchall()]
    if "reporting_manager" not in existing_columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN reporting_manager TEXT")
    if "work_location" not in existing_columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN work_location TEXT")

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            file_size INTEGER,
            file_type TEXT,
            extracted_text TEXT,
            extracted_json TEXT,
            comparison_json TEXT,
            ai_status TEXT DEFAULT 'Pending',
            verification_status TEXT DEFAULT 'Pending HR Review',
            discrepancy_notes TEXT,
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Ensure additional document columns exist in older schemas
    cursor.execute("PRAGMA table_info(documents)")
    existing_doc_cols = [row["name"] for row in cursor.fetchall()]
    if "file_size" not in existing_doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN file_size INTEGER")
    if "file_type" not in existing_doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN file_type TEXT")
    if "comparison_json" not in existing_doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN comparison_json TEXT")
    if "ai_status" not in existing_doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN ai_status TEXT DEFAULT 'Pending'")

    # Onboarding Checklist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            task_title TEXT NOT NULL,
            category TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            due_date TEXT,
            completed_at TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Audit Logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            employee_id INTEGER,
            action TEXT NOT NULL,
            reviewer TEXT,
            decision TEXT,
            review_notes TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)

    # Ensure older audit_logs schemas have required columns
    cursor.execute("PRAGMA table_info(audit_logs)")
    existing_audit_cols = [row["name"] for row in cursor.fetchall()]
    if "document_id" not in existing_audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN document_id INTEGER")
    if "reviewer" not in existing_audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN reviewer TEXT")
    if "decision" not in existing_audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN decision TEXT")
    if "review_notes" not in existing_audit_cols:
        cursor.execute("ALTER TABLE audit_logs ADD COLUMN review_notes TEXT")

    # Notifications table (Stage 9)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            dedup_key TEXT UNIQUE,
            reference_type TEXT,
            reference_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_employee_id ON notifications(employee_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_cat_prio ON notifications(category, priority)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_dedup_key ON notifications(dedup_key)")

    # Users table (Stage 11: Role-Based Authentication & Access Control)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
            employee_id INTEGER NULL,
            is_active INTEGER DEFAULT 1,
            force_password_change INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    conn.commit()

    # Seed sample records if empty
    cursor.execute("SELECT COUNT(*) AS count FROM employees")
    count = cursor.fetchone()["count"]

    if count == 0:
        seed_sample_data(cursor)
        conn.commit()

    # Seed default authentication accounts if empty
    seed_auth_accounts_if_empty(cursor)
    conn.commit()

    conn.close()


def seed_sample_data(cursor):
    """Seed sample data to give a realistic view upon initial launch."""
    sample_employees = [
        ("EMP-1001", "Sarah Jenkins", "sarah.j@company.com", "+1-555-0192", "Engineering", "Senior Software Engineer", "2026-11-01", "Alex Rivera (VP Eng)", "San Francisco, CA (HQ)", "In Progress"),
        ("EMP-1002", "Michael Chang", "michael.c@company.com", "+1-555-0143", "Product", "Product Manager", "2026-11-03", "Rachel Adams (Head of Product)", "New York, NY", "Pending HR Review"),
        ("EMP-1003", "Priya Sharma", "priya.s@company.com", "+1-555-0188", "Design", "Product Designer", "2026-10-25", "Liam Patel (Lead Designer)", "Remote - US", "In Progress"),
        ("EMP-1004", "David Miller", "david.m@company.com", "+1-555-0131", "Analytics", "Data Analyst", "2026-10-15", "Elena Rostova (Data Director)", "Chicago, IL", "Completed"),
        ("EMP-1005", "Elena Rostova", "elena.r@company.com", "+1-555-0174", "Engineering", "DevOps Engineer", "2026-11-05", "Alex Rivera (VP Eng)", "Remote - Global", "In Progress"),
    ]

    cursor.executemany("""
        INSERT INTO employees (employee_code, name, email, phone, department, role, join_date, reporting_manager, work_location, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_employees)

    sample_documents = [
        (1, "Passport / ID", "sarah_passport.pdf", "Pending HR Review", "AI extracted: Name matches. Expiry date valid."),
        (1, "Offer Letter Signed", "sarah_offer_signed.pdf", "Approved", "Verified signature."),
        (2, "ID Document", "michael_id.pdf", "Pending HR Review", "Awaiting HR manual review."),
        (3, "Degree Certificate", "priya_degree.pdf", "Approved", "Verified."),
        (3, "Tax Forms", "priya_tax_w4.pdf", "Pending HR Review", "Needs HR signature confirmation."),
        (4, "ID Card", "david_id.pdf", "Approved", "All onboarding requirements completed."),
    ]

    cursor.executemany("""
        INSERT INTO documents (employee_id, document_type, file_name, verification_status, discrepancy_notes)
        VALUES (?, ?, ?, ?, ?)
    """, sample_documents)

    sample_tasks = [
        (1, "HR Orientation Call", "Orientation", 1, "2026-11-02"),
        (1, "Workstation & Laptop Provisioning", "IT Setup", 1, "2026-11-02"),
        (1, "ID Verification by HR", "Compliance", 0, "2026-11-03"),
        (2, "HR Welcome & Overview", "Orientation", 0, "2026-11-04"),
        (2, "Tax & Benefits Enrollment", "Finance", 0, "2026-11-05"),
        (3, "Design Tool Licenses Access", "IT Setup", 1, "2026-10-26"),
        (4, "All Onboarding Milestones Complete", "General", 1, "2026-10-20"),
    ]

    cursor.executemany("""
        INSERT INTO checklist_tasks (employee_id, task_title, category, is_completed, due_date)
        VALUES (?, ?, ?, ?, ?)
    """, sample_tasks)


def seed_auth_accounts_if_empty(cursor):
    """
    Seeds a default HR administrator account if the users table is empty.
    Uses bcrypt for secure password hashing. The default admin credentials are:
        Email:    admin@onboardai.com
        Password: Admin@123
    The force_password_change flag is set so the admin must change their
    password on first login.
    """
    cursor.execute("SELECT COUNT(*) AS count FROM users")
    user_count = cursor.fetchone()["count"]

    if user_count == 0:
        default_email = "admin@onboardai.com"
        default_username = "admin"
        default_password = "Admin@123"

        password_hash, salt = hash_password(default_password)

        cursor.execute("""
            INSERT OR IGNORE INTO users (email, username, password_hash, salt, role, is_active, force_password_change)
            VALUES (?, ?, ?, ?, 'admin', 1, 1)
        """, (default_email, default_username, password_hash, salt))


def generate_next_employee_code() -> str:
    """Generates the next unique sequential employee code, e.g. EMP-1006."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_code FROM employees WHERE employee_code LIKE 'EMP-%'")
    rows = cursor.fetchall()
    conn.close()

    max_num = 1000
    for row in rows:
        code = row["employee_code"]
        if code:
            parts = code.split("-")
            if len(parts) >= 2 and parts[1].isdigit():
                num = int(parts[1])
                if num > max_num:
                    max_num = num

    return f"EMP-{max_num + 1}"


def check_email_exists(email: str) -> bool:
    """Checks if an employee with the specified email already exists in the database."""
    if not email:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM employees WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))", (email,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def register_new_employee(employee_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Registers a new employee into SQLite with duplicate checks and initial onboarding checklist tasks.
    
    Returns:
        (success: bool, message: str, employee_record: dict)
    """
    name = employee_data.get("name", "").strip()
    email = employee_data.get("email", "").strip().lower()
    phone = employee_data.get("phone", "").strip()
    department = employee_data.get("department", "").strip()
    role = employee_data.get("role", "").strip()
    join_date = str(employee_data.get("join_date", "")).strip()
    reporting_manager = employee_data.get("reporting_manager", "").strip()
    work_location = employee_data.get("work_location", "").strip()
    status = employee_data.get("status", "In Progress").strip()

    # Required field validation
    if not name:
        return False, "Full Name is required.", {}
    if not email:
        return False, "Work Email is required.", {}
    if not department:
        return False, "Department is required.", {}
    if not role:
        return False, "Job Role is required.", {}
    if not join_date:
        return False, "Joining Date is required.", {}

    # Email format validation
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        return False, f"Invalid email format: '{email}'. Please provide a valid email address.", {}

    # Duplicate email check
    if check_email_exists(email):
        return False, f"An employee with the email address '{email}' is already registered.", {}

    # Generate unique employee code
    employee_code = employee_data.get("employee_code")
    if not employee_code:
        employee_code = generate_next_employee_code()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO employees (
                employee_code, name, email, phone, department, role, 
                join_date, reporting_manager, work_location, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            employee_code, name, email, phone, department, role,
            join_date, reporting_manager, work_location, status
        ))
        employee_id = cursor.lastrowid

        # Seed standard onboarding checklist tasks for this employee
        default_tasks = [
            (employee_id, "Upload Official ID / Passport Document", "Documentation", 0, join_date),
            (employee_id, "Sign & Submit Employment Agreement", "Documentation", 0, join_date),
            (employee_id, "Complete Tax & Direct Deposit Banking Forms", "Finance & HR", 0, join_date),
            (employee_id, "Workstation & IT Equipment Provisioning", "IT Setup", 0, join_date),
            (employee_id, "HR Welcome & Orientation Walkthrough", "Orientation", 0, join_date),
            (employee_id, f"1-on-1 Introduction with {reporting_manager or 'Reporting Manager'}", "Orientation", 0, join_date),
        ]

        cursor.executemany("""
            INSERT INTO checklist_tasks (employee_id, task_title, category, is_completed, due_date)
            VALUES (?, ?, ?, ?, ?)
        """, default_tasks)

        conn.commit()

        new_employee = {
            "id": employee_id,
            "employee_code": employee_code,
            "name": name,
            "email": email,
            "phone": phone,
            "department": department,
            "role": role,
            "join_date": join_date,
            "reporting_manager": reporting_manager,
            "work_location": work_location,
            "status": status
        }
        return True, f"Employee '{name}' registered successfully with ID: {employee_code}", new_employee

    except sqlite3.IntegrityError as e:
        conn.rollback()
        return False, f"Database integrity violation: {str(e)}", {}
    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {str(e)}", {}
    finally:
        conn.close()


def get_dashboard_metrics():
    """Fetch summary metrics for the HR Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM employees")
    total_employees = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS in_progress FROM employees WHERE status = 'In Progress'")
    in_progress = cursor.fetchone()["in_progress"]

    cursor.execute("SELECT COUNT(*) AS pending_docs FROM documents WHERE verification_status = 'Pending HR Review'")
    pending_docs = cursor.fetchone()["pending_docs"]

    cursor.execute("SELECT COUNT(*) AS completed FROM employees WHERE status = 'Completed'")
    completed = cursor.fetchone()["completed"]

    conn.close()

    return {
        "total_employees": total_employees,
        "in_progress": in_progress,
        "pending_docs": pending_docs,
        "completed": completed
    }


def get_recent_onboardings(limit=5):
    """Retrieve the most recent onboarding employees."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id, e.employee_code, e.name, e.email, e.phone, e.department, e.role, e.join_date,
               e.reporting_manager, e.work_location, e.status,
               (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id AND d.verification_status = 'Pending HR Review') AS pending_docs,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 1) AS completed_tasks,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) AS total_tasks
        FROM employees e
        ORDER BY e.id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_department_breakdown():
    """Retrieve count of onboarding employees by department."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT department, COUNT(*) AS count
        FROM employees
        GROUP BY department
        ORDER BY count DESC
    """)

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_employees(search_term: Optional[str] = None, department: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all employees matching search criteria and filters,
    including their progress stats (completed/total tasks, pending docs).
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT e.id, e.employee_code, e.name, e.email, e.phone, e.department, e.role, e.join_date,
               e.reporting_manager, e.work_location, e.status, e.created_at,
               (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id AND d.verification_status = 'Pending HR Review') AS pending_docs,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 1) AS completed_tasks,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) AS total_tasks
        FROM employees e
        WHERE 1=1
    """
    params: List[Any] = []

    if search_term and search_term.strip():
        term = f"%{search_term.strip().lower()}%"
        query += " AND (LOWER(e.name) LIKE ? OR LOWER(e.email) LIKE ? OR LOWER(e.employee_code) LIKE ?)"
        params.extend([term, term, term])

    if department and department != "All Departments":
        query += " AND e.department = ?"
        params.append(department)

    if status and status != "All Statuses":
        query += " AND e.status = ?"
        params.append(status)

    query += " ORDER BY e.id DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves single employee record by ID with task and document summary counts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.employee_code, e.name, e.email, e.phone, e.department, e.role, e.join_date,
               e.reporting_manager, e.work_location, e.status, e.created_at,
               (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id AND d.verification_status = 'Pending HR Review') AS pending_docs,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 1) AS completed_tasks,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) AS total_tasks
        FROM employees e
        WHERE e.id = ?
    """, (employee_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_employee_by_code(employee_code: str) -> Optional[Dict[str, Any]]:
    """Retrieves single employee record by code with task and document summary counts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.employee_code, e.name, e.email, e.phone, e.department, e.role, e.join_date,
               e.reporting_manager, e.work_location, e.status, e.created_at,
               (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id AND d.verification_status = 'Pending HR Review') AS pending_docs,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 1) AS completed_tasks,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) AS total_tasks
        FROM employees e
        WHERE e.employee_code = ?
    """, (employee_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_employee_tasks(employee_id: int) -> List[Dict[str, Any]]:
    """Returns all checklist tasks for a specific employee."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_title, category, is_completed, due_date, completed_at
        FROM checklist_tasks
        WHERE employee_id = ?
        ORDER BY is_completed ASC, id ASC
    """, (employee_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_employee_documents(employee_id: int) -> List[Dict[str, Any]]:
    """Returns all documents for a specific employee."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, document_type, file_name, file_path, verification_status, discrepancy_notes, created_at
        FROM documents
        WHERE employee_id = ?
        ORDER BY id DESC
    """, (employee_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_employee(employee_id: int, updated_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates an employee record with validation and duplicate email check."""
    name = updated_data.get("name", "").strip()
    email = updated_data.get("email", "").strip().lower()
    phone = updated_data.get("phone", "").strip()
    department = updated_data.get("department", "").strip()
    role = updated_data.get("role", "").strip()
    join_date = str(updated_data.get("join_date", "")).strip()
    reporting_manager = updated_data.get("reporting_manager", "").strip()
    work_location = updated_data.get("work_location", "").strip()
    status = updated_data.get("status", "In Progress").strip()

    if not name:
        return False, "Full Name is required."
    if not email:
        return False, "Work Email is required."

    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        return False, f"Invalid email format: '{email}'."

    conn = get_connection()
    cursor = conn.cursor()

    # Prevent assigning an email already belonging to another employee
    cursor.execute("SELECT id FROM employees WHERE LOWER(TRIM(email)) = LOWER(TRIM(?)) AND id != ?", (email, employee_id))
    if cursor.fetchone():
        conn.close()
        return False, f"Email address '{email}' is already registered to another employee."

    try:
        cursor.execute("""
            UPDATE employees
            SET name = ?, email = ?, phone = ?, department = ?, role = ?,
                join_date = ?, reporting_manager = ?, work_location = ?, status = ?
            WHERE id = ?
        """, (name, email, phone, department, role, join_date, reporting_manager, work_location, status, employee_id))
        conn.commit()
        return True, "Employee profile updated successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update employee: {str(e)}"
    finally:
        conn.close()


def update_employee_status(employee_id: int, new_status: str) -> Tuple[bool, str]:
    """Updates onboarding status for an employee."""
    if not new_status:
        return False, "Status cannot be empty."
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE employees SET status = ? WHERE id = ?", (new_status.strip(), employee_id))
        conn.commit()
        return True, f"Status updated to '{new_status}' successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update status: {str(e)}"
    finally:
        conn.close()


def delete_employee(employee_id: int) -> Tuple[bool, str]:
    """
    Safely deletes an employee and all associated checklist tasks and documents.
    All deletions occur inside a single transaction to prevent orphaned records.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Delete related documents
        cursor.execute("DELETE FROM documents WHERE employee_id = ?", (employee_id,))
        # Delete related checklist tasks
        cursor.execute("DELETE FROM checklist_tasks WHERE employee_id = ?", (employee_id,))
        # Delete related audit logs
        cursor.execute("DELETE FROM audit_logs WHERE employee_id = ?", (employee_id,))
        # Delete related notifications (Stage 9)
        cursor.execute("DELETE FROM notifications WHERE employee_id = ?", (employee_id,))
        # Delete the employee record
        cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        conn.commit()
        return True, "Employee and all associated records have been permanently deleted."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to delete employee: {str(e)}"
    finally:
        conn.close()


def get_all_departments() -> List[str]:
    """Returns a list of distinct departments from database plus defaults."""
    default_depts = [
        "Engineering", "Product", "Design", "Analytics",
        "Human Resources", "Finance & Legal", "Marketing", "Sales", "Operations"
    ]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != ''")
    rows = cursor.fetchall()
    conn.close()
    db_depts = [row["department"] for row in rows]
    all_depts = sorted(list(set(default_depts + db_depts)))
    return all_depts


def get_all_statuses() -> List[str]:
    """Returns distinct statuses present in database or standard choices."""
    standard_statuses = ["In Progress", "Pending HR Review", "Completed", "On Hold"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT status FROM employees WHERE status IS NOT NULL AND status != ''")
    rows = cursor.fetchall()
    conn.close()
    db_statuses = [row["status"] for row in rows]
    all_statuses = sorted(list(set(standard_statuses + db_statuses)))
    return all_statuses


def save_uploaded_document(doc_data: Dict[str, Any]) -> int:
    """
    Saves metadata, extracted text, AI JSON, and comparison data for an uploaded document.
    
    Returns:
        document_id: int
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO documents (
            employee_id, document_type, file_name, file_path, file_size, file_type,
            extracted_text, extracted_json, comparison_json, ai_status,
            verification_status, discrepancy_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_data.get("employee_id"),
        doc_data.get("document_type", "General Document"),
        doc_data.get("file_name"),
        doc_data.get("file_path"),
        doc_data.get("file_size", 0),
        doc_data.get("file_type", "UNKNOWN"),
        doc_data.get("extracted_text", ""),
        doc_data.get("extracted_json", "{}"),
        doc_data.get("comparison_json", "{}"),
        doc_data.get("ai_status", "Pending"),
        doc_data.get("verification_status", "Pending HR Review"),
        doc_data.get("discrepancy_notes", "")
    ))

    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def get_documents_by_employee(employee_id: int) -> List[Dict[str, Any]]:
    """Returns all documents uploaded for a specific employee."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, employee_id, document_type, file_name, file_path, file_size, file_type,
               extracted_text, extracted_json, comparison_json, ai_status,
               verification_status, discrepancy_notes, reviewed_by, reviewed_at, created_at
        FROM documents
        WHERE employee_id = ?
        ORDER BY id DESC
    """, (employee_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_document_by_id(document_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves single document record by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.employee_id, d.document_type, d.file_name, d.file_path, d.file_size, d.file_type,
               d.extracted_text, d.extracted_json, d.comparison_json, d.ai_status,
               d.verification_status, d.discrepancy_notes, d.reviewed_by, d.reviewed_at, d.created_at,
               e.name AS employee_name, e.employee_code, e.department, e.role, e.email, e.phone
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        WHERE d.id = ?
    """, (document_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_document_review(
    document_id: int,
    extracted_json: str,
    discrepancy_notes: str,
    verification_status: str,
    reviewed_by: str = "HR Operations"
) -> Tuple[bool, str]:
    """
    Updates document extraction results and HR review findings.
    Keeps audit timestamp and reviewer details.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE documents
            SET extracted_json = ?,
                discrepancy_notes = ?,
                verification_status = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (extracted_json, discrepancy_notes, verification_status, reviewed_by, document_id))
        conn.commit()
        return True, "Document review and corrected fields saved successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to save document review: {str(e)}"
    finally:
        conn.close()


def get_all_documents_with_employee_info(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns the latest uploaded documents joined with employee details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.employee_id, d.document_type, d.file_name, d.file_path, d.file_size, d.file_type,
               d.ai_status, d.verification_status, d.discrepancy_notes, d.created_at,
               e.name AS employee_name, e.employee_code, e.department
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        ORDER BY d.id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_document_review_metrics() -> Dict[str, int]:
    """
    Computes count breakdown for the Centralized Document Review Queue:
    Pending HR Review, Approved, Rejected, Correction Requested, Total.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM documents WHERE verification_status = 'Pending HR Review'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE verification_status = 'Approved'")
    approved = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE verification_status = 'Rejected'")
    rejected = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE verification_status = 'Correction Requested'")
    correction_requested = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents")
    total = cursor.fetchone()[0]

    conn.close()

    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "correction_requested": correction_requested,
        "total": total
    }


def get_review_queue_documents(
    search_term: Optional[str] = None,
    document_type: Optional[str] = None,
    review_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves documents joined with employee details for the Centralized Review Queue.
    Supports parameterized filtering by search term, document type, and review status.
    Prioritizes 'Pending HR Review' and 'Correction Requested' items.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT d.id, d.employee_id, d.document_type, d.file_name, d.file_path, d.file_size, d.file_type,
               d.extracted_text, d.extracted_json, d.comparison_json, d.ai_status,
               d.verification_status, d.discrepancy_notes, d.reviewed_by, d.reviewed_at, d.created_at,
               e.name AS employee_name, e.employee_code, e.department, e.role, e.email, e.phone,
               e.join_date, e.reporting_manager, e.work_location
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        WHERE 1=1
    """
    params: List[Any] = []

    if search_term and search_term.strip():
        term = f"%{search_term.strip().lower()}%"
        query += " AND (LOWER(e.name) LIKE ? OR LOWER(e.employee_code) LIKE ? OR LOWER(d.file_name) LIKE ?)"
        params.extend([term, term, term])

    if document_type and document_type != "All Document Types":
        query += " AND d.document_type = ?"
        params.append(document_type)

    if review_status and review_status != "All Statuses":
        query += " AND d.verification_status = ?"
        params.append(review_status)

    query += """
        ORDER BY 
            CASE 
                WHEN d.verification_status = 'Pending HR Review' THEN 0 
                WHEN d.verification_status = 'Correction Requested' THEN 1 
                WHEN d.verification_status = 'Rejected' THEN 2 
                ELSE 3 
            END,
            d.id DESC
    """

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def submit_hr_document_decision(
    document_id: int,
    decision: str,
    review_notes: str,
    reviewer: str = "HR Operations Specialist"
) -> Tuple[bool, str]:
    """
    Records an explicit HR decision ('Approved', 'Rejected', 'Correction Requested').
    Requires mandatory review notes for rejection and correction requests.
    Records an audit log entry in audit_logs inside a single atomic database transaction.
    """
    valid_decisions = ["Approved", "Rejected", "Correction Requested"]
    if decision not in valid_decisions:
        return False, f"Invalid decision '{decision}'. Must be one of {valid_decisions}."

    notes_clean = review_notes.strip() if review_notes else ""
    if decision in ["Rejected", "Correction Requested"] and not notes_clean:
        return False, f"Review notes are required when setting status to '{decision}'. Please provide feedback or reasons."

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Fetch document and employee details
        cursor.execute("SELECT employee_id, file_name, document_type FROM documents WHERE id = ?", (document_id,))
        doc_row = cursor.fetchone()
        if not doc_row:
            conn.close()
            return False, f"Document #{document_id} not found."

        employee_id = doc_row["employee_id"]
        file_name = doc_row["file_name"]
        doc_type = doc_row["document_type"]

        # 1. Update documents record
        cursor.execute("""
            UPDATE documents
            SET verification_status = ?,
                discrepancy_notes = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (decision, notes_clean, reviewer, document_id))

        # 2. Record in audit_logs
        cursor.execute("""
            INSERT INTO audit_logs (
                document_id, employee_id, action, reviewer, decision, review_notes, details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            employee_id,
            f"Document {decision}",
            reviewer,
            decision,
            notes_clean,
            f"Reviewer {reviewer} set status to '{decision}' for document '{file_name}' ({doc_type})."
        ))

        conn.commit()
        return True, f"Document #{document_id} ('{file_name}') successfully updated to '{decision}'."

    except Exception as e:
        conn.rollback()
        return False, f"Failed to record review decision: {str(e)}"
    finally:
        conn.close()


def get_document_audit_trail(document_id: int) -> List[Dict[str, Any]]:
    """Returns chronological audit log records for a specific document."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.document_id, a.employee_id, a.action, a.reviewer,
               a.decision, a.review_notes, a.details, a.created_at,
               e.name AS employee_name, e.employee_code
        FROM audit_logs a
        LEFT JOIN employees e ON a.employee_id = e.id
        WHERE a.document_id = ?
        ORDER BY a.id DESC
    """, (document_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Returns all workforce compliance audit trail entries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.document_id, a.employee_id, a.action, a.reviewer,
               a.decision, a.review_notes, a.details, a.created_at,
               e.name AS employee_name, e.employee_code,
               d.file_name, d.document_type
        FROM audit_logs a
        LEFT JOIN employees e ON a.employee_id = e.id
        LEFT JOIN documents d ON a.document_id = d.id
        ORDER BY a.id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Stage 6: Smart Onboarding Checklist Functions ─────────────────────────────


def get_checklist_summary_all_employees() -> List[Dict[str, Any]]:
    """
    Returns per-employee checklist progress summary for all employees.
    Used by the checklist overview table.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            e.id,
            e.employee_code,
            e.name,
            e.department,
            e.role,
            e.status,
            COUNT(t.id) AS total_tasks,
            SUM(CASE WHEN t.is_completed = 1 THEN 1 ELSE 0 END) AS completed_tasks,
            SUM(CASE WHEN t.is_completed = 0 THEN 1 ELSE 0 END) AS pending_tasks
        FROM employees e
        LEFT JOIN checklist_tasks t ON t.employee_id = e.id
        GROUP BY e.id
        ORDER BY e.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_checklist_task(employee_id: int, task_title: str, category: str, due_date: Optional[str] = None) -> Tuple[bool, str]:
    """
    Adds a new custom task to an employee's onboarding checklist.

    Returns:
        (success: bool, message: str)
    """
    task_title = task_title.strip() if task_title else ""
    category = category.strip() if category else ""

    if not task_title:
        return False, "Task title is required."
    if not category:
        return False, "Category is required."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO checklist_tasks (employee_id, task_title, category, is_completed, due_date)
            VALUES (?, ?, ?, 0, ?)
        """, (employee_id, task_title, category, due_date or None))
        conn.commit()
        return True, f"Task '{task_title}' added successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to add task: {str(e)}"
    finally:
        conn.close()


def toggle_checklist_task(task_id: int, is_completed: bool) -> Tuple[bool, str]:
    """
    Marks a checklist task as complete or incomplete.
    Records completed_at timestamp when marking complete; clears it when marking incomplete.

    Returns:
        (success: bool, message: str)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if is_completed:
            cursor.execute("""
                UPDATE checklist_tasks
                SET is_completed = 1, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (task_id,))
        else:
            cursor.execute("""
                UPDATE checklist_tasks
                SET is_completed = 0, completed_at = NULL
                WHERE id = ?
            """, (task_id,))
        conn.commit()
        status_label = "complete" if is_completed else "incomplete"
        return True, f"Task marked as {status_label}."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update task: {str(e)}"
    finally:
        conn.close()


def delete_checklist_task(task_id: int) -> Tuple[bool, str]:
    """
    Permanently deletes a single checklist task by its ID.

    Returns:
        (success: bool, message: str)
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM checklist_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return True, "Task removed from checklist."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to delete task: {str(e)}"
    finally:
        conn.close()


def get_task_categories() -> List[str]:
    """Returns a combined list of default and existing task categories."""
    default_categories = [
        "Orientation", "Documentation", "IT Setup",
        "Finance & HR", "Compliance", "Training", "General"
    ]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM checklist_tasks WHERE category IS NOT NULL AND category != ''")
    rows = cursor.fetchall()
    conn.close()
    db_cats = [row["category"] for row in rows]
    all_cats = sorted(list(set(default_categories + db_cats)))
    return all_cats


# ── Stage 7: Onboarding Progress Tracking Functions ───────────────────────────


def get_progress_overview_metrics() -> Dict[str, int]:
    """
    Returns workforce-level onboarding progress metrics for the overview dashboard.

    Counts:
      - total_employees
      - completed: employees with status='Completed'
      - in_progress: employees with status='In Progress'
      - pending_review: employees who have at least one document with
                        verification_status='Pending HR Review'
      - overdue_tasks: employees who have at least one uncompleted task
                       whose due_date < today
    """
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'Completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'In Progress'")
    in_progress = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT employee_id) FROM documents
        WHERE verification_status = 'Pending HR Review'
    """)
    pending_review = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT employee_id) FROM checklist_tasks
        WHERE is_completed = 0
          AND due_date IS NOT NULL
          AND due_date < ?
    """, (today,))
    overdue_tasks = cursor.fetchone()[0]

    conn.close()
    return {
        "total_employees": total,
        "completed": completed,
        "in_progress": in_progress,
        "pending_review": pending_review,
        "overdue_tasks": overdue_tasks,
    }


def get_all_employees_progress(
    search_term: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    overdue_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Returns per-employee onboarding progress data used in the progress table.

    For each employee, includes:
      - Basic profile (code, name, department, role, join_date, status)
      - total_docs, approved_docs, pending_docs, rejected_docs
      - total_tasks, completed_tasks, overdue_tasks
      - has_overdue: 1 if the employee has overdue tasks
      - progress_pct: integer 0-100 computed as described in calculate_progress()

    Computation is done in SQL aggregates to minimise round-trips.
    Supports search by name/code, department filter, status filter, and
    overdue-only filter (applied via Python after the query).
    """
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT
            e.id,
            e.employee_code,
            e.name,
            e.email,
            e.department,
            e.role,
            e.join_date,
            e.status,
            e.created_at,

            -- Document counts
            COUNT(DISTINCT d.id)                                                        AS total_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Approved'
                                THEN d.id END)                                          AS approved_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Pending HR Review'
                                THEN d.id END)                                          AS pending_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Rejected'
                                THEN d.id END)                                          AS rejected_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Correction Requested'
                                THEN d.id END)                                          AS correction_docs,

            -- Checklist counts
            COUNT(DISTINCT t.id)                                                        AS total_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 1 THEN t.id END)                 AS completed_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 0
                                 AND t.due_date IS NOT NULL
                                 AND t.due_date < :today THEN t.id END)                AS overdue_tasks

        FROM employees e
        LEFT JOIN documents d      ON d.employee_id = e.id
        LEFT JOIN checklist_tasks t ON t.employee_id = e.id
        WHERE 1=1
    """
    params: Dict[str, Any] = {"today": today}

    if search_term and search_term.strip():
        term = f"%{search_term.strip().lower()}%"
        query += """
            AND (LOWER(e.name) LIKE :search
              OR LOWER(e.employee_code) LIKE :search
              OR LOWER(e.email) LIKE :search)
        """
        params["search"] = term

    if department and department not in ("All Departments", ""):
        query += " AND e.department = :dept"
        params["dept"] = department

    if status and status not in ("All Statuses", ""):
        query += " AND e.status = :status"
        params["status"] = status

    query += " GROUP BY e.id ORDER BY e.id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        r["progress_pct"] = _calculate_progress_pct(r)
        r["has_overdue"] = 1 if r["overdue_tasks"] > 0 else 0
        results.append(r)

    if overdue_only:
        results = [r for r in results if r["has_overdue"]]

    return results


def _calculate_progress_pct(row: Dict[str, Any]) -> int:
    """
    Calculates a single integer 0–100 progress percentage for one employee.

    Scoring model (four equally-weighted stages, 25 points each):

      Stage 1 – Registration (25 pts)
          Always 25 if the employee record exists (calling this function implies it does).

      Stage 2 – Document Submission (25 pts)
          25 if total_docs >= 1, else 0.
          Rationale: submission is a binary yes/no gate.

      Stage 3 – HR Document Review (25 pts)
          = 25 × (approved_docs / total_docs)  if total_docs > 0
          = 0                                  if total_docs == 0
          Partial credit is given for partial approval so HR can track
          mixed states (some approved, some still pending).
          A document is NOT counted as approved merely because AI extracted it;
          only rows with verification_status='Approved' count.

      Stage 4 – Checklist Completion (25 pts)
          = 25 × (completed_tasks / total_tasks)  if total_tasks > 0
          = 0                                      if total_tasks == 0

    Total is rounded to the nearest integer and clamped to [0, 100].
    """
    # Stage 1: registration always complete for existing employees
    s1 = 25

    # Stage 2: at least one document uploaded
    total_docs = row.get("total_docs", 0) or 0
    s2 = 25 if total_docs >= 1 else 0

    # Stage 3: proportion of documents that are HR-approved
    approved_docs = row.get("approved_docs", 0) or 0
    s3 = round(25 * (approved_docs / total_docs)) if total_docs > 0 else 0

    # Stage 4: proportion of checklist tasks completed
    total_tasks = row.get("total_tasks", 0) or 0
    completed_tasks = row.get("completed_tasks", 0) or 0
    s4 = round(25 * (completed_tasks / total_tasks)) if total_tasks > 0 else 0

    return min(100, max(0, s1 + s2 + s3 + s4))


def get_employee_progress_detail(employee_id: int) -> Optional[Dict[str, Any]]:
    """
    Returns full progress detail for one employee, used in the detail view.

    Includes everything from get_all_employees_progress() plus:
      - reporting_manager, work_location, phone
      - stage_scores dict (s1..s4 and total)
      - overdue task list (id, task_title, category, due_date)
    """
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT
            e.id, e.employee_code, e.name, e.email, e.phone,
            e.department, e.role, e.join_date, e.status,
            e.reporting_manager, e.work_location, e.created_at,

            COUNT(DISTINCT d.id)                                                        AS total_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Approved'
                                THEN d.id END)                                          AS approved_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Pending HR Review'
                                THEN d.id END)                                          AS pending_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Rejected'
                                THEN d.id END)                                          AS rejected_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Correction Requested'
                                THEN d.id END)                                          AS correction_docs,

            COUNT(DISTINCT t.id)                                                        AS total_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 1 THEN t.id END)                 AS completed_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 0
                                 AND t.due_date IS NOT NULL
                                 AND t.due_date < :today THEN t.id END)                AS overdue_tasks

        FROM employees e
        LEFT JOIN documents d       ON d.employee_id = e.id
        LEFT JOIN checklist_tasks t  ON t.employee_id = e.id
        WHERE e.id = :emp_id
        GROUP BY e.id
    """, {"emp_id": employee_id, "today": today})

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    result = dict(row)
    result["progress_pct"] = _calculate_progress_pct(result)
    result["has_overdue"] = 1 if result["overdue_tasks"] > 0 else 0

    # Stage scores breakdown for display
    total_docs     = result.get("total_docs", 0) or 0
    approved_docs  = result.get("approved_docs", 0) or 0
    total_tasks    = result.get("total_tasks", 0) or 0
    completed_tasks = result.get("completed_tasks", 0) or 0

    result["stage_scores"] = {
        "s1": 25,
        "s2": 25 if total_docs >= 1 else 0,
        "s3": round(25 * (approved_docs / total_docs)) if total_docs > 0 else 0,
        "s4": round(25 * (completed_tasks / total_tasks)) if total_tasks > 0 else 0,
    }

    # Overdue task details
    cursor.execute("""
        SELECT id, task_title, category, due_date
        FROM checklist_tasks
        WHERE employee_id = ?
          AND is_completed = 0
          AND due_date IS NOT NULL
          AND due_date < ?
        ORDER BY due_date ASC
    """, (employee_id, today))
    result["overdue_task_list"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return result


def get_employee_timeline(employee_id: int) -> List[Dict[str, Any]]:
    """
    Returns a chronologically ordered timeline of key onboarding events for one employee.

    Sources (uses only real timestamps from the database):
      - Employee registration  (employees.created_at)
      - Document uploads       (documents.created_at)
      - HR review decisions    (audit_logs.created_at  where decision IS NOT NULL)
      - Checklist completions  (checklist_tasks.completed_at where is_completed=1)

    Each event dict contains: { event_type, title, detail, timestamp }
    """
    conn = get_connection()
    cursor = conn.cursor()
    events: List[Dict[str, Any]] = []

    # 1. Registration event
    cursor.execute(
        "SELECT name, employee_code, created_at FROM employees WHERE id = ?",
        (employee_id,)
    )
    emp_row = cursor.fetchone()
    if emp_row and emp_row["created_at"]:
        events.append({
            "event_type": "registration",
            "title": "Employee Registered",
            "detail": f"{emp_row['name']} ({emp_row['employee_code']}) added to the system.",
            "timestamp": emp_row["created_at"],
        })

    # 2. Document upload events
    cursor.execute("""
        SELECT document_type, file_name, verification_status, created_at
        FROM documents
        WHERE employee_id = ?
        ORDER BY created_at ASC
    """, (employee_id,))
    for doc in cursor.fetchall():
        if doc["created_at"]:
            events.append({
                "event_type": "document_upload",
                "title": f"Document Uploaded: {doc['document_type']}",
                "detail": doc["file_name"] or "—",
                "timestamp": doc["created_at"],
            })

    # 3. HR review decisions (from audit_logs)
    cursor.execute("""
        SELECT a.decision, a.reviewer, a.review_notes, a.created_at,
               d.document_type, d.file_name
        FROM audit_logs a
        LEFT JOIN documents d ON a.document_id = d.id
        WHERE a.employee_id = ?
          AND a.decision IS NOT NULL
          AND a.decision != ''
        ORDER BY a.created_at ASC
    """, (employee_id,))
    for entry in cursor.fetchall():
        if entry["created_at"]:
            doc_label = entry["document_type"] or "Document"
            events.append({
                "event_type": f"review_{entry['decision'].lower().replace(' ', '_')}",
                "title": f"HR Decision: {entry['decision']} — {doc_label}",
                "detail": (
                    f"Reviewer: {entry['reviewer'] or 'HR'}. "
                    + (f"Notes: {entry['review_notes']}" if entry["review_notes"] else "")
                ).strip(),
                "timestamp": entry["created_at"],
            })

    # 4. Checklist task completions
    cursor.execute("""
        SELECT task_title, category, completed_at
        FROM checklist_tasks
        WHERE employee_id = ?
          AND is_completed = 1
          AND completed_at IS NOT NULL
        ORDER BY completed_at ASC
    """, (employee_id,))
    for task in cursor.fetchall():
        events.append({
            "event_type": "task_completed",
            "title": f"Task Completed: {task['task_title']}",
            "detail": f"Category: {task['category']}",
            "timestamp": task["completed_at"],
        })

    conn.close()

    # Sort chronologically; put None timestamps last
    events.sort(key=lambda e: e["timestamp"] or "9999")
    return events



# New: Overdue checklist tasks helper
def get_overdue_checklist_tasks() -> List[Dict[str, Any]]:
    """Fetch employees with overdue, incomplete checklist tasks.
    Returns list of dicts with employee_id, employee_code, name, overdue_task_count.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.id AS employee_id, e.employee_code, e.name,
               COUNT(t.id) AS overdue_tasks
        FROM employees e
        JOIN checklist_tasks t ON e.id = t.employee_id
        WHERE t.is_completed = 0
          AND t.due_date IS NOT NULL
          AND DATE(t.due_date) < DATE('now')
        GROUP BY e.id, e.employee_code, e.name
        HAVING overdue_tasks > 0
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Stage 8: Analytics & Reporting Functions ──────────────────────────────────


def get_min_max_join_dates() -> Tuple[Optional[str], Optional[str]]:
    """Returns the minimum and maximum join_date/created_at found in employees table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(COALESCE(NULLIF(join_date, ''), DATE(created_at))) AS min_d,
               MAX(COALESCE(NULLIF(join_date, ''), DATE(created_at))) AS max_d
        FROM employees
    """)
    row = cursor.fetchone()
    conn.close()
    if row and row["min_d"] and row["max_d"]:
        return str(row["min_d"]), str(row["max_d"])
    return None, None


def get_analytics_filtered_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves filtered workforce data, checklist tasks, and documents for Analytics and Reporting.
    Computes all KPI aggregates, performance statistics, department metrics, monthly trends,
    and category task breakdowns.
    """
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Base query for filtered employees with document and task counts
    query = """
        SELECT
            e.id,
            e.employee_code,
            e.name,
            e.email,
            e.phone,
            e.department,
            e.role,
            e.join_date,
            e.status,
            e.reporting_manager,
            e.work_location,
            e.created_at,

            -- Document counts
            COUNT(DISTINCT d.id) AS total_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Approved' THEN d.id END) AS approved_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Pending HR Review' THEN d.id END) AS pending_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Rejected' THEN d.id END) AS rejected_docs,
            COUNT(DISTINCT CASE WHEN d.verification_status = 'Correction Requested' THEN d.id END) AS correction_docs,

            -- Checklist counts
            COUNT(DISTINCT t.id) AS total_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 1 THEN t.id END) AS completed_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 0 THEN t.id END) AS pending_tasks,
            COUNT(DISTINCT CASE WHEN t.is_completed = 0
                                 AND t.due_date IS NOT NULL
                                 AND t.due_date < :today THEN t.id END) AS overdue_tasks,

            -- Timestamps for completion duration analysis
            MAX(CASE WHEN t.is_completed = 1 THEN t.completed_at END) AS last_task_completed,
            MAX(d.reviewed_at) AS last_doc_reviewed

        FROM employees e
        LEFT JOIN documents d ON d.employee_id = e.id
        LEFT JOIN checklist_tasks t ON t.employee_id = e.id
        WHERE 1=1
    """
    params: Dict[str, Any] = {"today": today}

    if department and department not in ("All Departments", ""):
        query += " AND e.department = :dept"
        params["dept"] = department

    if status and status not in ("All Statuses", ""):
        query += " AND e.status = :status"
        params["status"] = status

    if start_date:
        query += " AND COALESCE(NULLIF(e.join_date, ''), DATE(e.created_at)) >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND COALESCE(NULLIF(e.join_date, ''), DATE(e.created_at)) <= :end_date"
        params["end_date"] = end_date

    query += " GROUP BY e.id ORDER BY e.id DESC"

    cursor.execute(query, params)
    emp_rows = cursor.fetchall()
    employees: List[Dict[str, Any]] = []
    emp_ids: List[int] = []

    for row in emp_rows:
        r = dict(row)
        r["progress_pct"] = _calculate_progress_pct(r)
        r["has_overdue"] = 1 if r["overdue_tasks"] > 0 else 0
        employees.append(r)
        emp_ids.append(r["id"])

    # 2. Documents for filtered employees
    documents: List[Dict[str, Any]] = []
    if emp_ids:
        placeholders = ",".join("?" for _ in emp_ids)
        cursor.execute(f"""
            SELECT d.id, d.employee_id, d.document_type, d.file_name, d.file_size, d.file_type,
                   d.ai_status, d.verification_status, d.discrepancy_notes, d.reviewed_by, d.reviewed_at, d.created_at,
                   e.name AS employee_name, e.employee_code, e.department
            FROM documents d
            JOIN employees e ON d.employee_id = e.id
            WHERE d.employee_id IN ({placeholders})
            ORDER BY d.id DESC
        """, emp_ids)
        documents = [dict(r) for r in cursor.fetchall()]

    # 3. Tasks for filtered employees
    tasks: List[Dict[str, Any]] = []
    if emp_ids:
        placeholders = ",".join("?" for _ in emp_ids)
        cursor.execute(f"""
            SELECT t.id, t.employee_id, t.task_title, t.category, t.is_completed, t.due_date, t.completed_at,
                   e.name AS employee_name, e.employee_code, e.department
            FROM checklist_tasks t
            JOIN employees e ON t.employee_id = e.id
            WHERE t.employee_id IN ({placeholders})
            ORDER BY t.id ASC
        """, emp_ids)
        for r in cursor.fetchall():
            task_dict = dict(r)
            is_overdue = 1 if (not task_dict["is_completed"] and task_dict["due_date"] and str(task_dict["due_date"]) < today) else 0
            task_dict["is_overdue"] = is_overdue
            tasks.append(task_dict)

    conn.close()

    # 4. Compute KPI Metrics
    total_employees = len(employees)
    completed_employees = sum(1 for e in employees if e["status"] == "Completed")
    in_progress_employees = sum(1 for e in employees if e["status"] == "In Progress")
    pending_status_employees = sum(1 for e in employees if e["status"] not in ("Completed", "In Progress"))

    total_docs = len(documents)
    approved_docs = sum(1 for d in documents if d["verification_status"] == "Approved")
    pending_docs = sum(1 for d in documents if d["verification_status"] == "Pending HR Review")
    rejected_docs = sum(1 for d in documents if d["verification_status"] == "Rejected")
    correction_docs = sum(1 for d in documents if d["verification_status"] == "Correction Requested")

    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t["is_completed"])
    pending_tasks = sum(1 for t in tasks if not t["is_completed"])
    overdue_tasks = sum(1 for t in tasks if t["is_overdue"])
    employees_with_overdue = sum(1 for e in employees if e["overdue_tasks"] > 0)

    # 5. Performance Analysis
    overall_completion_rate = round((completed_employees / total_employees) * 100, 1) if total_employees > 0 else 0.0
    avg_progress_pct = round(sum(e["progress_pct"] for e in employees) / total_employees, 1) if total_employees > 0 else 0.0

    reviewed_docs_count = approved_docs + rejected_docs + correction_docs
    doc_approval_rate = round((approved_docs / reviewed_docs_count) * 100, 1) if reviewed_docs_count > 0 else 0.0
    doc_rejection_rate = round((rejected_docs / reviewed_docs_count) * 100, 1) if reviewed_docs_count > 0 else 0.0
    task_completion_rate = round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0.0

    # Average onboarding completion time using available timestamps (strictly no fake dates!)
    completion_durations: List[float] = []
    for e in employees:
        if e["status"] == "Completed":
            # Attempt to find start and completion timestamps
            start_ts = e["created_at"] or e["join_date"]
            end_ts = e["last_task_completed"] or e["last_doc_reviewed"]
            if start_ts and end_ts:
                try:
                    s_dt = datetime.fromisoformat(str(start_ts).strip())
                    e_dt = datetime.fromisoformat(str(end_ts).strip())
                    days = (e_dt - s_dt).total_seconds() / 86400.0
                    if days >= 0:
                        completion_durations.append(round(days, 1))
                except Exception:
                    pass

    avg_completion_days = round(sum(completion_durations) / len(completion_durations), 1) if completion_durations else None
    completion_time_samples = len(completion_durations)

    # 6. Department-wise breakdown
    dept_map: Dict[str, Dict[str, Any]] = {}
    for e in employees:
        dept = e["department"] or "Unassigned"
        if dept not in dept_map:
            dept_map[dept] = {
                "department": dept,
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "overdue_tasks": 0,
                "progress_sum": 0,
            }
        dept_map[dept]["total"] += 1
        if e["status"] == "Completed":
            dept_map[dept]["completed"] += 1
        elif e["status"] == "In Progress":
            dept_map[dept]["in_progress"] += 1
        dept_map[dept]["overdue_tasks"] += e["overdue_tasks"]
        dept_map[dept]["progress_sum"] += e["progress_pct"]

    department_stats: List[Dict[str, Any]] = []
    for dept, data in sorted(dept_map.items()):
        total = data["total"]
        rate = round((data["completed"] / total) * 100, 1) if total > 0 else 0.0
        avg_prog = round(data["progress_sum"] / total, 1) if total > 0 else 0.0
        department_stats.append({
            "department": dept,
            "total_employees": total,
            "completed": data["completed"],
            "in_progress": data["in_progress"],
            "completion_rate_pct": rate,
            "avg_progress_pct": avg_prog,
            "overdue_tasks": data["overdue_tasks"],
        })

    # 7. Monthly employee onboarding trends
    month_map: Dict[str, int] = {}
    for e in employees:
        jd = e["join_date"] or str(e["created_at"])[:10]
        if jd and len(jd) >= 7:
            m_key = jd[:7]  # YYYY-MM
            month_map[m_key] = month_map.get(m_key, 0) + 1

    monthly_trends = [{"month": m, "new_hires": count} for m, count in sorted(month_map.items())]

    # 8. Category-wise checklist completion stats
    cat_map: Dict[str, Dict[str, int]] = {}
    for t in tasks:
        cat = t["category"] or "General"
        if cat not in cat_map:
            cat_map[cat] = {"total": 0, "completed": 0, "pending": 0, "overdue": 0}
        cat_map[cat]["total"] += 1
        if t["is_completed"]:
            cat_map[cat]["completed"] += 1
        else:
            cat_map[cat]["pending"] += 1
            if t["is_overdue"]:
                cat_map[cat]["overdue"] += 1

    category_task_stats: List[Dict[str, Any]] = []
    for cat, cdata in sorted(cat_map.items()):
        tot = cdata["total"]
        comp = cdata["completed"]
        rate = round((comp / tot) * 100, 1) if tot > 0 else 0.0
        category_task_stats.append({
            "category": cat,
            "total": tot,
            "completed": comp,
            "pending": cdata["pending"],
            "overdue": cdata["overdue"],
            "completion_rate_pct": rate,
        })

    return {
        "employees": employees,
        "documents": documents,
        "tasks": tasks,
        "kpis": {
            "total_employees": total_employees,
            "completed_employees": completed_employees,
            "in_progress_employees": in_progress_employees,
            "pending_status_employees": pending_status_employees,
            "total_documents": total_docs,
            "approved_documents": approved_docs,
            "pending_documents": pending_docs,
            "rejected_documents": rejected_docs,
            "correction_documents": correction_docs,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "overdue_tasks": overdue_tasks,
            "employees_with_overdue": employees_with_overdue,
        },
        "performance": {
            "overall_completion_rate": overall_completion_rate,
            "avg_progress_pct": avg_progress_pct,
            "doc_approval_rate": doc_approval_rate,
            "doc_rejection_rate": doc_rejection_rate,
            "task_completion_rate": task_completion_rate,
            "avg_completion_days": avg_completion_days,
            "completion_time_samples": completion_time_samples,
        },
        "department_stats": department_stats,
        "monthly_trends": monthly_trends,
        "category_task_stats": category_task_stats,
    }


# ── Stage 9: Notifications & Reminders Functions ──────────────────────────────

DEFAULT_NOTIFICATION_PRIORITIES = {
    "overdue_tasks": "High",
    "pending_approvals": "High",
    "rejected_documents": "High",
    "upcoming_deadlines": "Medium",
    "correction_requests": "Medium",
    "pending_submissions": "Low",
    "incomplete_onboarding": "Low",
}


def sync_system_notifications(
    priority_rules: Optional[Dict[str, str]] = None,
    upcoming_days: int = 7
) -> int:
    """
    Scans the current database state (documents, tasks, onboarding progress)
    and synchronizes pending notifications with deterministic deduplication keys.
    Prevents duplicate notifications on page reruns and preserves user's read status.
    Returns the number of new notifications created during this sync run.
    """
    p_rules = dict(DEFAULT_NOTIFICATION_PRIORITIES)
    if priority_rules:
        p_rules.update(priority_rules)

    conn = get_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_dt = datetime.now().date()
    new_notif_count = 0

    candidate_notifications: List[Tuple[Any, ...]] = []

    # 1. Documents awaiting HR approval (verification_status = 'Pending HR Review')
    cursor.execute("""
        SELECT d.id, d.employee_id, d.document_type, d.file_name,
               e.name AS employee_name, e.employee_code
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        WHERE d.verification_status = 'Pending HR Review'
    """)
    for row in cursor.fetchall():
        dedup = f"doc_pending_review_{row['id']}"
        title = f"Document Awaiting Review: {row['document_type']}"
        msg = f"Document '{row['file_name']}' ({row['document_type']}) for {row['employee_name']} ({row['employee_code']}) requires human HR verification."
        prio = p_rules.get("pending_approvals", "High")
        candidate_notifications.append((
            row["employee_id"], title, msg, "Document Review", prio, dedup, "document", row["id"]
        ))

    # 2. Rejected documents requiring attention (verification_status = 'Rejected')
    cursor.execute("""
        SELECT d.id, d.employee_id, d.document_type, d.file_name, d.discrepancy_notes,
               e.name AS employee_name, e.employee_code
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        WHERE d.verification_status = 'Rejected'
    """)
    for row in cursor.fetchall():
        dedup = f"doc_rejected_{row['id']}"
        title = f"Document Rejected: {row['document_type']}"
        reason = row["discrepancy_notes"] or "Compliance criteria not satisfied."
        msg = f"Document '{row['file_name']}' for {row['employee_name']} was rejected. Reason: {reason}"
        prio = p_rules.get("rejected_documents", "High")
        candidate_notifications.append((
            row["employee_id"], title, msg, "Document Review", prio, dedup, "document", row["id"]
        ))

    # 3. Correction requests awaiting employee action (verification_status = 'Correction Requested')
    cursor.execute("""
        SELECT d.id, d.employee_id, d.document_type, d.file_name, d.discrepancy_notes,
               e.name AS employee_name, e.employee_code
        FROM documents d
        JOIN employees e ON d.employee_id = e.id
        WHERE d.verification_status = 'Correction Requested'
    """)
    for row in cursor.fetchall():
        dedup = f"doc_correction_{row['id']}"
        title = f"Correction Requested: {row['document_type']}"
        notes = row["discrepancy_notes"] or "Update requested by HR reviewer."
        msg = f"Candidate update required for '{row['file_name']}' ({row['employee_name']}). Notes: {notes}"
        prio = p_rules.get("correction_requests", "Medium")
        candidate_notifications.append((
            row["employee_id"], title, msg, "Document Review", prio, dedup, "document", row["id"]
        ))

    # 4. Overdue checklist tasks (is_completed = 0 AND due_date < today)
    cursor.execute("""
        SELECT t.id, t.employee_id, t.task_title, t.category, t.due_date,
               e.name AS employee_name, e.employee_code
        FROM checklist_tasks t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.is_completed = 0
          AND t.due_date IS NOT NULL
          AND t.due_date < ?
    """, (today_str,))
    for row in cursor.fetchall():
        dedup = f"task_overdue_{row['id']}_{row['due_date']}"
        title = f"Overdue Milestone: {row['task_title']}"
        msg = f"Checklist task '{row['task_title']}' ({row['category']}) for {row['employee_name']} ({row['employee_code']}) passed deadline on {row['due_date']}."
        prio = p_rules.get("overdue_tasks", "High")
        candidate_notifications.append((
            row["employee_id"], title, msg, "Checklist Milestone", prio, dedup, "checklist_task", row["id"]
        ))

    # 5. Upcoming checklist deadlines (is_completed = 0 AND due_date >= today AND due_date <= today + upcoming_days)
    cursor.execute("""
        SELECT t.id, t.employee_id, t.task_title, t.category, t.due_date,
               e.name AS employee_name, e.employee_code
        FROM checklist_tasks t
        JOIN employees e ON t.employee_id = e.id
        WHERE t.is_completed = 0
          AND t.due_date IS NOT NULL
          AND t.due_date >= ?
    """, (today_str,))
    for row in cursor.fetchall():
        try:
            task_due_dt = datetime.fromisoformat(str(row["due_date"]).strip()).date()
            days_diff = (task_due_dt - today_dt).days
            if 0 <= days_diff <= upcoming_days:
                dedup = f"task_upcoming_{row['id']}_{row['due_date']}"
                title = f"Upcoming Deadline: {row['task_title']}"
                days_label = "today" if days_diff == 0 else f"in {days_diff} day{'s' if days_diff > 1 else ''}"
                msg = f"Milestone '{row['task_title']}' for {row['employee_name']} ({row['employee_code']}) is due {days_label} on {row['due_date']}."
                prio = p_rules.get("upcoming_deadlines", "Medium")
                candidate_notifications.append((
                    row["employee_id"], title, msg, "Checklist Milestone", prio, dedup, "checklist_task", row["id"]
                ))
        except Exception:
            pass

    # 6. Pending employee document submissions (employee in progress with 0 documents submitted)
    cursor.execute("""
        SELECT e.id, e.name, e.employee_code, e.join_date,
               (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id) AS doc_count
        FROM employees e
        WHERE e.status != 'Completed'
          AND (SELECT COUNT(*) FROM documents d WHERE d.employee_id = e.id) = 0
    """)
    for row in cursor.fetchall():
        dedup = f"emp_pending_docs_{row['id']}"
        title = f"Document Submission Pending: {row['name']}"
        msg = f"New hire {row['name']} ({row['employee_code']}) has not uploaded any onboarding compliance documents yet."
        prio = p_rules.get("pending_submissions", "Low")
        candidate_notifications.append((
            row["id"], title, msg, "Document Submission", prio, dedup, "employee", row["id"]
        ))

    # 7. Incomplete onboarding activities (status != 'Completed', tasks pending)
    cursor.execute("""
        SELECT e.id, e.name, e.employee_code, e.join_date,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) AS total_t,
               (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 1) AS comp_t
        FROM employees e
        WHERE e.status != 'Completed'
          AND (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id) > 0
          AND (SELECT COUNT(*) FROM checklist_tasks t WHERE t.employee_id = e.id AND t.is_completed = 0) > 0
    """)
    for row in cursor.fetchall():
        dedup = f"emp_incomplete_activities_{row['id']}"
        tot = row["total_t"]
        done = row["comp_t"]
        title = f"Incomplete Onboarding: {row['name']}"
        msg = f"{row['name']} ({row['employee_code']}) has {tot - done} incomplete onboarding tasks ({done}/{tot} complete)."
        prio = p_rules.get("incomplete_onboarding", "Low")
        candidate_notifications.append((
            row["id"], title, msg, "General Onboarding", prio, dedup, "employee", row["id"]
        ))

    # Insert candidate notifications with deduplication via INSERT OR IGNORE
    for c_item in candidate_notifications:
        cursor.execute("""
            INSERT OR IGNORE INTO notifications (
                employee_id, title, message, category, priority, is_read, dedup_key, reference_type, reference_id
            )
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, c_item)
        if cursor.rowcount > 0:
            new_notif_count += 1

    conn.commit()
    conn.close()
    return new_notif_count


def get_all_notifications(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    is_read: Optional[int] = None,
    search_term: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves all notifications joined with employee metadata.
    Supports filtering by category, priority, read status, and search query.
    Orders unread items and high priorities first.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT n.id, n.employee_id, n.title, n.message, n.category, n.priority,
               n.is_read, n.dedup_key, n.reference_type, n.reference_id, n.created_at,
               COALESCE(e.name, 'System / Unassigned') AS employee_name,
               COALESCE(e.employee_code, 'N/A') AS employee_code,
               COALESCE(e.department, 'Unassigned') AS department,
               COALESCE(e.role, 'N/A') AS role,
               COALESCE(e.status, 'N/A') AS employee_status
        FROM notifications n
        LEFT JOIN employees e ON n.employee_id = e.id
        WHERE 1=1
    """
    params: List[Any] = []

    if category and category != "All Categories":
        query += " AND n.category = ?"
        params.append(category)

    if priority and priority != "All Priorities":
        query += " AND n.priority = ?"
        params.append(priority)

    if is_read is not None:
        query += " AND n.is_read = ?"
        params.append(is_read)

    if employee_id is not None:
        query += " AND n.employee_id = ?"
        params.append(employee_id)

    if search_term and search_term.strip():
        term = f"%{search_term.strip().lower()}%"
        query += """
            AND (LOWER(n.title) LIKE ?
              OR LOWER(n.message) LIKE ?
              OR LOWER(COALESCE(e.name, '')) LIKE ?
              OR LOWER(COALESCE(e.employee_code, '')) LIKE ?)
        """
        params.extend([term, term, term, term])

    query += """
        ORDER BY
            n.is_read ASC,
            CASE
                WHEN n.priority = 'High' THEN 0
                WHEN n.priority = 'Medium' THEN 1
                ELSE 2
            END,
            n.id DESC
    """

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_notification_metrics() -> Dict[str, int]:
    """Returns overview summary counts for the Notification Center."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM notifications")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
    unread = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notifications WHERE priority = 'High'")
    high_prio = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM notifications
        WHERE category = 'Checklist Milestone' AND title LIKE '%Overdue%'
    """)
    overdue = cursor.fetchone()[0]

    conn.close()
    return {
        "total": total,
        "unread": unread,
        "high_priority": high_prio,
        "overdue": overdue,
    }


def get_unread_notification_count() -> int:
    """Returns the total number of unread notifications for badge rendering."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_notification_status(notification_id: int, is_read: bool) -> Tuple[bool, str]:
    """Updates the read/unread state of a single notification."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        val = 1 if is_read else 0
        cursor.execute("UPDATE notifications SET is_read = ? WHERE id = ?", (val, notification_id))
        conn.commit()
        status_text = "read" if is_read else "unread"
        return True, f"Notification #{notification_id} marked as {status_text}."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to update notification: {str(e)}"
    finally:
        conn.close()


def mark_all_notifications_status(
    is_read: bool,
    category: Optional[str] = None,
    priority: Optional[str] = None
) -> Tuple[bool, str]:
    """Bulk marks all notifications (or filtered subset) as read or unread."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        val = 1 if is_read else 0
        query = "UPDATE notifications SET is_read = ? WHERE 1=1"
        params: List[Any] = [val]

        if category and category != "All Categories":
            query += " AND category = ?"
            params.append(category)

        if priority and priority != "All Priorities":
            query += " AND priority = ?"
            params.append(priority)

        cursor.execute(query, tuple(params))
        count = cursor.rowcount
        conn.commit()
        status_text = "read" if is_read else "unread"
        return True, f"Marked {count} notification(s) as {status_text}."
    except Exception as e:
        conn.rollback()
        return False, f"Bulk update failed: {str(e)}"
    finally:
        conn.close()


def delete_notification(notification_id: int) -> Tuple[bool, str]:
    """Permanently deletes a notification from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
        conn.commit()
        return True, f"Notification #{notification_id} deleted."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to delete notification: {str(e)}"
    finally:
        conn.close()


def clear_all_notifications(read_only: bool = False) -> Tuple[bool, str]:
    """Deletes all notifications, or optionally only read notifications."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if read_only:
            cursor.execute("DELETE FROM notifications WHERE is_read = 1")
            msg = "All read notifications cleared."
        else:
            cursor.execute("DELETE FROM notifications")
            msg = "All notifications cleared."
        conn.commit()
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, f"Failed to clear notifications: {str(e)}"
    finally:
        conn.close()


