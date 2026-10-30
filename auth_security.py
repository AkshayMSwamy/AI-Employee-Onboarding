"""
Security and authentication helper module for OnboardAI (Stage 11).
Implements bcrypt password hashing, constant-time verification,
server-side role & ownership permission checks, and session timeout management.
"""

import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from functools import wraps


# ─────────────────────────────────────────────────────────────────────────────
# 1. PASSWORD HASHING & CRYPTOGRAPHY (bcrypt)
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password using bcrypt with an automatically-generated salt.
    Never stores plain-text passwords.

    The `salt` parameter is accepted for API compatibility with the database
    schema (which stores a salt column) but is NOT used by bcrypt – bcrypt
    embeds the salt inside the hash string itself. A random token is returned
    as the salt column value for schema compatibility.

    Args:
        password: Plaintext password (must not be empty).
        salt: Optional value for schema compatibility. Ignored by bcrypt.

    Returns:
        Tuple of (bcrypt_hash_string, salt_token)

    Raises:
        ValueError: If password is empty or None.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    # bcrypt generates its own per-hash salt internally
    # bcrypt has a 72-byte password limit; truncate gracefully
    password_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))

    # Return the hash as a UTF-8 string and a random token for the salt column
    salt_token = salt if salt else secrets.token_hex(16)
    return hashed.decode("utf-8"), salt_token


def verify_password(password: str, stored_hash: str, salt: str = "") -> bool:
    """
    Verifies a plaintext password against the stored bcrypt hash.
    Uses bcrypt's built-in constant-time comparison.

    The `salt` parameter is accepted for API compatibility but is not used –
    bcrypt extracts the salt from the stored hash automatically.

    Args:
        password: Plaintext password to verify.
        stored_hash: The bcrypt hash string from the database.
        salt: Ignored. Kept for API compatibility with the DB schema.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not password or not stored_hash:
        return False

    try:
        password_bytes = password.encode("utf-8")[:72]
        hash_bytes = stored_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except (ValueError, TypeError):
        # Malformed hash or encoding error
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates that a password meets minimum security requirements.

    Requirements:
        - At least 8 characters long
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit
        - Contains at least one special character

    Returns:
        Tuple of (is_valid, message)
    """
    if not password:
        return False, "Password cannot be empty."

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit."

    special_chars = set("!@#$%^&*()_+-=[]{}|;':\",./<>?`~")
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character."

    return True, "Password meets all requirements."


# ─────────────────────────────────────────────────────────────────────────────
# 2. SERVER-SIDE PERMISSION & ACCESS CONTROL CHECKS
# ─────────────────────────────────────────────────────────────────────────────

class PermissionDeniedError(Exception):
    """Raised when an operation violates role-based access control or ownership rules."""
    pass


def require_role(actor_user: Optional[Dict[str, Any]], allowed_roles: List[str]) -> bool:
    """
    Enforces that actor_user possesses one of the allowed roles.
    Raises PermissionDeniedError if unauthorized or unauthenticated.

    Args:
        actor_user: Dict containing at least {'role': str}. Typically from session state.
        allowed_roles: List of role strings that are permitted (e.g. ['admin', 'employee']).

    Returns:
        True if the user has an allowed role.

    Raises:
        PermissionDeniedError: If user is None or role is not in allowed_roles.
    """
    if actor_user is None:
        raise PermissionDeniedError("Authentication required: No active user session.")

    role = (actor_user.get("role") or "").lower()
    if not role:
        raise PermissionDeniedError(
            f"Access denied: User has no role assigned. Required: {allowed_roles}"
        )
    allowed_lower = [r.lower() for r in allowed_roles]

    if role not in allowed_lower:
        raise PermissionDeniedError(
            f"Access denied: User role '{role}' is not authorized. Required: {allowed_roles}"
        )
    return True


def require_employee_access(actor_user: Optional[Dict[str, Any]], target_employee_id: int) -> bool:
    """
    Enforces that actor_user is an HR Admin, OR an employee accessing their own record.
    Prevents employee ID manipulation across all protected boundaries.

    Args:
        actor_user: Dict containing at least {'role': str, 'employee_id': int|None}.
        target_employee_id: The employee record being accessed.

    Returns:
        True if access is permitted.

    Raises:
        PermissionDeniedError: If user is None, or is an employee trying to access
                               another employee's data.
    """
    if not actor_user:
        raise PermissionDeniedError("Authentication required: No active user session.")

    role = (actor_user.get("role") or "").lower()
    if role == "admin":
        return True

    user_emp_id = actor_user.get("employee_id")
    if user_emp_id is None or int(user_emp_id) != int(target_employee_id):
        raise PermissionDeniedError(
            f"Access violation: Employee #{user_emp_id} is not permitted to access or modify Employee #{target_employee_id} data."
        )
    return True


def check_role(actor_user: Optional[Dict[str, Any]], allowed_roles: List[str]) -> bool:
    """
    Non-raising version of require_role. Returns True/False without exceptions.
    Useful for conditional UI rendering while keeping server-side checks via require_role.

    Args:
        actor_user: Dict containing at least {'role': str}.
        allowed_roles: List of permitted role strings.

    Returns:
        True if the user has an allowed role, False otherwise.
    """
    if not actor_user:
        return False

    role = (actor_user.get("role") or "").lower()
    allowed_lower = [r.lower() for r in allowed_roles]
    return role in allowed_lower


# ─────────────────────────────────────────────────────────────────────────────
# 3. SESSION TIMEOUT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_SESSION_TIMEOUT_MINUTES = 30


def is_session_expired(last_activity_iso: Optional[str], timeout_minutes: int = DEFAULT_SESSION_TIMEOUT_MINUTES) -> bool:
    """
    Determines if the session has exceeded the inactivity timeout window.

    Args:
        last_activity_iso: ISO 8601 timestamp string of the last user activity.
        timeout_minutes: Maximum allowed inactivity in minutes.

    Returns:
        True if the session is expired or the timestamp is invalid/missing.
    """
    if not last_activity_iso:
        return True

    try:
        last_dt = datetime.fromisoformat(last_activity_iso)
        timeout_delta = timedelta(minutes=timeout_minutes)
        return datetime.now() - last_dt > timeout_delta
    except Exception:
        return True


def get_current_timestamp_iso() -> str:
    """Returns the current timestamp in ISO format."""
    return datetime.now().isoformat()
