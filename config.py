"""
Configuration settings for AI-Powered Employee Onboarding System.
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "onboarding.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# App branding
APP_TITLE = "OnboardAI"
APP_SUBTITLE = "AI-Powered Employee Onboarding System"
APP_ICON = "🏢"

# AI / Ollama Configuration (configurable via environment variables)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

# Document types supported
DOCUMENT_TYPES = [
    "Resume / CV",
    "Government ID / Passport",
    "Offer Letter",
    "Educational Degree / Transcript",
    "Direct Deposit / Bank Form",
    "Aadhaar Card",
    "PAN Card",
    "Passport",
    "Driving Licence",
    "Educational Certificate",
    "Other Supporting Documents"
]

# Centralized list of reporting managers for dropdown selection
REPORTING_MANAGERS = [
    "Ananya Rao",
    "Rahul Sharma",
    "Priya Nair",
    "Arjun Kumar",
    "Sneha Reddy"
]

# Employee Onboarding Statuses
STATUS_NEW = "Registered"
STATUS_IN_PROGRESS = "In Progress"
STATUS_PENDING_REVIEW = "Pending HR Review"
STATUS_APPROVED = "Approved"
STATUS_COMPLETED = "Completed"
