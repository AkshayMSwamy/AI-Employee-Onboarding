# OnboardAI — AI-Powered Employee Onboarding System

**OnboardAI** is a production-grade, human-in-the-loop workforce onboarding intelligence suite built with Python, Streamlit, SQLite, and local AI (Ollama with Google Gemma 3 1B). It provides Human Resources operations teams with end-to-end automation for new hire intake, document extraction, credential cross-verification, compliance milestone tracking, workforce analytics, and real-time SLA reminders.

---

## 📌 Problem Statement
Traditional corporate employee onboarding is fragmented across disparate systems, manual spreadsheets, and physical paperwork. HR professionals spend an excessive amount of time:
- Manually transcribing candidate credentials from PDFs, Word documents, and spreadsheets.
- Detecting discrepancies between submitted certificates and official application data.
- Tracking multi-department onboarding milestones (IT setup, compliance, finance, orientation).
- Managing document compliance deadlines and regulatory audit logs.
- Reporting workforce readiness to department executives.

---

## 🎯 Objectives
1. **Accelerate Turnaround:** Automate document parsing and structured field extraction using local privacy-preserving AI.
2. **Ensure Human Oversight:** Mandate human HR verification for all compliance decisions—AI accelerates data extraction but never makes autonomous hiring decisions.
3. **Prevent Discrepancies:** Cross-verify submitted documents against registered employee records in real time with visual matching badges.
4. **Enforce Milestone Accountability:** Track departmental checklist tasks with automated overdue detection and progress scoring.
5. **Provide Executive Transparency:** Deliver interactive analytics, department turnaround metrics, and one-click audit-ready Excel and PDF exports.
6. **Proactive SLA Reminders:** Centralize alerts for pending reviews, upcoming deadlines, and overdue tasks with automated deduplication.

---

## 🛠️ Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Frontend UI** | Streamlit (>=1.30.0) | Interactive, responsive web application framework with custom CSS theming |
| **Data Visualizations** | Plotly (>=5.18.0) | Interactive donut charts, grouped/stacked bars, and trend analysis |
| **Relational Database** | SQLite 3 (`onboarding.db`) | ACID-compliant relational store with foreign keys, indexes, and cascade integrity |
| **Local AI Engine** | Ollama with Gemma 3 1B | Privacy-preserving on-premises structured information extraction (no cloud data leaks) |
| **Fallback Intelligence** | Python Regex & Heuristics | Zero-downtime rule-based parser that executes when Ollama is offline |
| **Document Processing** | PyMuPDF (1.24+), python-docx, openpyxl, xlrd | Multi-format parsing for PDF, DOCX, XLSX, and legacy XLS files |
| **Report Generation** | PyMuPDF (`pymupdf`) & openpyxl | Programmatic multi-page executive PDF rendering and styled Excel workbooks |

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT APPLICATION (UI)                     │
│  [Dashboard] [Registration] [Management] [Doc Upload] [Doc Review]    │
│  [Checklist] [Progress Tracking] [Analytics & Reports] [Notifications] │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LOGIC                            │
│  modules/                  utils/                 database/            │
│  ├── dashboard.py          ├── document_parser.py └── db.py            │
│  ├── employee_registration ├── ai_extractor.py       (Schema, Seed,    │
│  ├── employee_management   └── styling.py             Indexes, Queries,│
│  ├── document_processing                              Deduplication)   │
│  ├── document_review                                                   │
│  ├── smart_checklist                                                   │
│  ├── onboarding_progress                                               │
│  ├── analytics_reporting                                               │
│  └── notifications.py                                                  │
└───────────────┬────────────────────────────┬───────────────────────────┘
                │                            │
                ▼                            ▼
┌──────────────────────────────┐ ┌───────────────────────────────────────┐
│     DOCUMENT & AI ENGINES    │ │          PERSISTENCE LAYER            │
│  • PyMuPDF (PDF Parser)      │ │  • SQLite 3 Database (onboarding.db)   │
│  • python-docx (DOCX)        │ │    ├── employees                      │
│  • openpyxl / xlrd (Excel)   │ │    ├── documents                      │
│  • Ollama (Gemma 3 1B)       │ │    ├── checklist_tasks                │
│  • Rule-Based Fallback       │ │    ├── audit_logs                     │
│  • Comparison Engine         │ │    └── notifications                  │
│                              │ │  • Secure Storage: data/uploads/      │
└──────────────────────────────┘ └───────────────────────────────────────┘
```

---

## 🔄 Core Workflow

```
1. REGISTRATION ───► 2. MILESTONE INIT ───► 3. DOCUMENT UPLOAD
   New Hire Profile    Auto-provision 6         PDF / DOCX / XLSX / XLS
   & Unique EMP Code   Department Tasks         Saved securely in data/uploads
           │                                                │
           ▼                                                ▼
6. HR COMPLIANCE ◄── 5. COMPARISON ENGINE ◄─── 4. AI EXTRACTION
   Approve / Reject /   Cross-check doc vs        Local Gemma 3 1B with
   Correction Request   registration records      Rule-based Fallback
           │
           ▼
7. CHECKLIST COMPLETION ──► 8. REAL-TIME PROGRESS ──► 9. ANALYTICS & EXPORTS
   Department Milestones       Weighted 4-stage score    KPIs, Overdue Alerts,
   & Timestamp Tracking        (0% to 100%)              Excel (.xlsx) & PDF Reports
```

---

## 🌟 Features of All 10 Stages

### Stage 1: Foundation & HR Operations Dashboard
- Executive KPI overview cards (Total Hires, In-Progress, Pending Reviews, Completed).
- Recent onboarding pipeline roster with status indicators.
- Departmental headcount breakdown.
- System readiness indicators (Database, AI Engine, Document Parsers).

### Stage 2: Employee Registration & Workforce Intake
- Comprehensive new hire registration form with strict input validation.
- Auto-generation of unique sequential employee codes (`EMP-1001`, `EMP-1002`).
- Duplicate email prevention.
- Automatic provisioning of standard onboarding compliance milestones upon registration.

### Stage 3: Employee Management & Workforce Directory
- Search across candidates by full name, employee ID, or email.
- Multi-parameter filtering by department and onboarding status.
- Complete profile view showing role, contact details, assigned manager, and location.
- Profile editing with live database persistence.
- Safe cascading deletion (removes associated documents, tasks, logs, and alerts inside an atomic transaction).

### Stage 4: AI-Powered Multi-Format Document Processing
- Multi-format file uploader supporting PDF, DOCX, XLSX, and XLS (up to 15MB).
- Deterministic file collision prevention (guaranteed zero accidental file overwriting).
- Integration with local Ollama daemon running Google Gemma 3 1B.
- Instant, zero-downtime fallback to rule-based regex and heuristic extraction when Ollama is offline.
- Real-time comparison matrix matching extracted data against employee registration profiles.

### Stage 5: Centralized Document Review & HR Approval Queue
- Cross-workforce document review queue with status filters (Pending, Approved, Rejected, Correction Needed).
- Human-in-the-loop decision interface: explicit Approve, Reject, or Correction Requested actions.
- Mandatory review notes enforced for all rejections and correction requests.
- Permanent compliance audit logging in `audit_logs` tracking reviewer identity, timestamps, and findings.
- Guardrail: AI extraction never marks identity as verified; only authorized HR decisions grant approval.

### Stage 6: Smart Onboarding Checklist
- Departmental checklist tasks grouped into categories (Orientation, Documentation, IT Setup, Finance & HR, Compliance, Training, General).
- Per-employee interactive task completion toggles with automatic timestamp recording.
- Custom milestone task creation with category selection and calendar due dates.
- Task deletion and overdue task detection (`due_date < today`).
- Workforce-wide checklist completion table.

### Stage 7: Onboarding Progress Tracking & Employee Journey
- Standardized, documented 4-stage progress scoring model (Registration: 25%, Document Submission: 25%, HR Review: 25%, Checklist Milestones: 25%).
- Detailed employee progress view displaying pending activities, completed milestones, and overdue items.
- Chronological timeline tracking milestone events using real timestamps (no synthetic dates).
- Search and filtering by employee ID, department, onboarding status, and overdue flags.

### Stage 8: Workforce Analytics & Executive Reporting
- High-level KPI dashboard displaying total hires, completion rates, pending reviews, and overdue tasks.
- 5 interactive Plotly visualizations:
  1. Completed vs. In-Progress Employee Status Breakdown (Donut chart).
  2. Department-Wise Onboarding Status (Grouped bar chart).
  3. Document Verification Status Distribution (Donut chart).
  4. Checklist Completion Statistics by Category (Stacked bar chart).
  5. Monthly Employee Intake Volume Trends (Bar chart).
- Deep-dive performance metrics including average completion turnaround in days (strictly computed from real timestamps).
- Multi-parameter filtering (joining window date range, department, status).
- 4 audit-ready export downloads:
  - **Employee Summary (.xlsx)**: Full workforce profile, progress %, and task breakdown.
  - **Document Review Audit (.xlsx)**: Extraction status, HR decisions, reviewer notes, and dates.
  - **Checklist Milestones Report (.xlsx)**: Task titles, categories, completion dates, and overdue flags.
  - **Executive Analytics Report (.pdf)**: Styled multi-page report with KPI cards, department tables, and escalation notices.

### Stage 9: Notifications & Reminders Center
- Real-time notification generation across 7 business event types:
  - Pending employee document submissions (Low priority).
  - Documents awaiting HR review (High priority).
  - Rejected documents requiring attention (High priority).
  - Correction requests awaiting employee action (Medium priority).
  - Overdue checklist milestones (High priority).
  - Upcoming checklist deadlines within configurable window (Medium priority).
  - Incomplete onboarding reminders (Low priority).
- Strict deduplication architecture (`dedup_key UNIQUE`) preventing duplicate alerts across page reruns.
- Single-click Mark Read / Mark Unread toggles, bulk actions, and dismissals.
- Sidebar unread notification alert badge (`🔔 X Unread Alerts`).
- Configurable priority rules and upcoming deadline threshold slider (1–14 days).

### Stage 10: Final Testing, Optimization & Deployment Preparation
- End-to-end integration verification covering the complete 14-step onboarding journey.
- Database security hardening (foreign keys, cascading cleanup, SQL injection defenses).
- Document parser resilience testing (PDF, DOCX, XLSX, XLS, empty files, non-existent paths).
- AI fallback testing verifying uninterrupted operation whether Ollama is online or offline.
- Database backup creation (`onboarding_backup_stage10.db`).
- Clean, documented deployment guide.

---

## 📁 Project Directory Structure

```text
employee_onboarding/
│
├── app.py                              # Main Streamlit application & navigation router
├── config.py                           # App configuration, file paths, Ollama settings
├── database.py                         # Backwards-compatibility bridge re-exporting database.db
├── onboarding.db                       # Active SQLite 3 relational database
├── onboarding_backup_stage10.db        # Safe SQLite backup created in Stage 10
├── requirements.txt                    # Validated, minimal Python dependencies
├── README.md                           # Master documentation & deployment guide
│
├── assets/
│   └── style.css                       # Modern CSS styling for cards, headers, & tables
│
├── data/
│   ├── onboarding.db                   # Secondary database reference path
│   └── uploads/                        # Secure local storage for uploaded candidate files
│
├── database/
│   ├── __init__.py
│   └── db.py                           # SQLite schema, indexes, queries, & business logic
│
├── modules/
│   ├── __init__.py
│   ├── dashboard.py                   # Stage 1: HR Operations Dashboard
│   ├── employee_registration.py       # Stage 2: Employee Registration
│   ├── employee_management.py         # Stage 3: Employee Directory & Cascade Deletion
│   ├── document_processing.py         # Stage 4: Document Parsing & AI Comparison
│   ├── document_review.py             # Stage 5: Centralized HR Approval Queue & Audit
│   ├── smart_checklist.py             # Stage 6: Onboarding Checklist & Categories
│   ├── onboarding_progress.py         # Stage 7: Progress Tracking & Timeline
│   ├── analytics_reporting.py         # Stage 8: Plotly Analytics & Excel/PDF Reports
│   └── notifications.py               # Stage 9: Notification Center & Reminders
│
├── utils/
│   ├── __init__.py
│   ├── document_parser.py             # PyMuPDF, python-docx, openpyxl, xlrd parsers
│   ├── ai_extractor.py                # Ollama Gemma 3 1B client + rule-based fallback
│   └── styling.py                     # HTML badge and card formatting utilities
│
└── tests/
    ├── test_stage8_analytics.py       # Stage 8 automated verification suite
    ├── test_stage9_notifications.py   # Stage 9 automated verification suite
    └── test_stage10_full_integration.py # Stage 10 comprehensive end-to-end integration suite
```

---

## 💾 Database Schema

The system uses an embedded SQLite database (`onboarding.db`) with five core tables:

1. **`employees`**:
   `id`, `employee_code` (UNIQUE), `name`, `email` (UNIQUE), `phone`, `department`, `role`, `join_date`, `reporting_manager`, `work_location`, `status`, `created_at`.
2. **`documents`**:
   `id`, `employee_id` (FK), `document_type`, `file_name`, `file_path`, `file_size`, `file_type`, `extracted_text`, `extracted_json`, `comparison_json`, `ai_status`, `verification_status`, `discrepancy_notes`, `reviewed_by`, `reviewed_at`, `created_at`.
3. **`checklist_tasks`**:
   `id`, `employee_id` (FK), `task_title`, `category`, `is_completed`, `due_date`, `completed_at`.
4. **`audit_logs`**:
   `id`, `document_id` (FK), `employee_id` (FK), `action`, `reviewer`, `decision`, `review_notes`, `details`, `created_at`.
5. **`notifications`**:
   `id`, `employee_id` (FK), `title`, `message`, `category`, `priority`, `is_read`, `dedup_key` (UNIQUE), `reference_type`, `reference_id`, `created_at`.

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed.
- Git (optional, for version control).
- (Optional for local AI) [Ollama](https://ollama.ai) installed and running.

### 2. Clone or Navigate to the Project Directory
```bash
cd C:\Users\DELL\Desktop\employee_onboarding
```

### 3. Set Up Virtual Environment
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🤖 Ollama & Google Gemma 3 1B Setup

OnboardAI is configured to leverage Google's lightweight, high-performance **Gemma 3 1B** model running locally via Ollama.

### 1. Download and Start Ollama
Download and install Ollama from [https://ollama.ai](https://ollama.ai).
Start the Ollama daemon:
```bash
ollama serve
```

### 2. Pull the Gemma 3 1B Model
```bash
ollama pull gemma3:1b
```

### 3. Verify Local AI Availability
Test the model via CLI:
```bash
ollama run gemma3:1b "Hello, summarize onboarding compliance."
```

> **Note on Zero-Downtime Fallback:**
> If Ollama is offline or unavailable, OnboardAI **automatically switches to its built-in rule-based regex & heuristic extraction engine**. All documents will continue to be parsed, compared, and reviewed without crashing or interrupting HR operations.

---

## 🚀 How to Run the Application

Start the Streamlit application:
```bash
streamlit run app.py
```
The interface will launch in your default web browser at `http://localhost:8501`.

---

## 🧪 Testing Instructions

Run the automated test suites using the active virtual environment:

### Run Stage 8 Analytics Tests
```bash
.\venv\Scripts\python.exe test_stage8_analytics.py
```

### Run Stage 9 Notifications Tests
```bash
.\venv\Scripts\python.exe test_stage9_notifications.py
```

### Run Stage 10 Comprehensive End-to-End Test Suite
```bash
.\venv\Scripts\python.exe test_stage10_full_integration.py
```

---

## ⚠️ Known Limitations
1. **Document Authenticity vs. Information Extraction:** Local AI extracts text and compares data fields, but does not perform cryptographic digital signature verification or forensic document tampering checks. Human review remains mandatory.
2. **Scanned Image Documents (OCR):** PyMuPDF extracts text streams from digital PDFs. Scanned documents that contain flat bitmap images without embedded text streams require an OCR pre-processor (such as Tesseract or EasyOCR).
3. **Outbound Push Notifications:** The notification center currently provides in-app alerts and triage. Integration with external SMTP email or SMS gateways can be layered into the existing notification queue.

---

## 🔮 Future Enhancements
- **Tesseract OCR Integration:** Optical Character Recognition for scanned physical ID cards and camera photos.
- **SSO & Role-Based Access Control (RBAC):** Granular permissions separating HR Administrators, Department Hiring Managers, and Candidate Self-Service Portals.
- **E-Signature Gateway:** Direct integration with digital signature APIs (DocuSign, Adobe Sign) for employment contract execution.
- **Automated IT Provisioning Sidecars:** Webhooks triggering Google Workspace / Microsoft 365 account creation upon HR onboarding completion.

---

*OnboardAI — Human-in-the-Loop Workforce Intelligence • Stage 10 Completed & Verified.*
