"""
Test suite for utils/auth_security.py — OnboardAI Stage 11 authentication utilities.

Tests cover:
  1. Password hashing (bcrypt)
  2. Password verification (correct / wrong / empty / malformed)
  3. Password strength validation
  4. Role-based access control (require_role, check_role)
  5. Employee access ownership checks (require_employee_access)
  6. Session timeout management
  7. Integration with database seed (seed_auth_accounts_if_empty)
"""

import os
import sys
import sqlite3
import pytest
from datetime import datetime, timedelta

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.auth_security import (
    hash_password,
    verify_password,
    validate_password_strength,
    require_role,
    require_employee_access,
    check_role,
    PermissionDeniedError,
    is_session_expired,
    get_current_timestamp_iso,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PASSWORD HASHING TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestHashPassword:
    """Tests for the hash_password function using bcrypt."""

    def test_returns_tuple_of_two_strings(self):
        """hash_password must return (hash_str, salt_str)."""
        result = hash_password("SecureP@ss1")
        assert isinstance(result, tuple)
        assert len(result) == 2
        hash_val, salt_val = result
        assert isinstance(hash_val, str)
        assert isinstance(salt_val, str)

    def test_hash_starts_with_bcrypt_prefix(self):
        """bcrypt hashes always start with $2b$ (or $2a$/$2y$)."""
        hash_val, _ = hash_password("TestPass1!")
        assert hash_val.startswith("$2")

    def test_hash_is_not_plaintext(self):
        """The hash must never equal the plaintext password."""
        password = "MySecret@99"
        hash_val, _ = hash_password(password)
        assert hash_val != password

    def test_different_calls_produce_different_hashes(self):
        """Two calls with the same password must produce different hashes (unique salts)."""
        h1, _ = hash_password("SamePass1!")
        h2, _ = hash_password("SamePass1!")
        assert h1 != h2

    def test_salt_token_is_generated_when_not_provided(self):
        """When no salt is given, a random hex salt token is returned."""
        _, salt = hash_password("AnyPass1!")
        assert len(salt) == 32  # 16 bytes hex = 32 chars

    def test_salt_token_preserved_when_provided(self):
        """When a salt is explicitly provided, it's returned as-is."""
        _, salt = hash_password("AnyPass1!", salt="custom_salt_value")
        assert salt == "custom_salt_value"

    def test_empty_password_raises_value_error(self):
        """Empty or None password must raise ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password(None)

    def test_unicode_password(self):
        """Passwords with unicode characters should hash correctly."""
        hash_val, _ = hash_password("Pässwörd@1")
        assert hash_val.startswith("$2")

    def test_long_password(self):
        """bcrypt truncates at 72 bytes but should not crash."""
        long_pw = "A" * 100 + "@1a"
        hash_val, _ = hash_password(long_pw)
        assert hash_val.startswith("$2")


# ─────────────────────────────────────────────────────────────────────────────
# 2. PASSWORD VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyPassword:
    """Tests for the verify_password function."""

    def test_correct_password_verifies(self):
        """A correct password must return True."""
        password = "CorrectHorse@1"
        hash_val, salt = hash_password(password)
        assert verify_password(password, hash_val, salt) is True

    def test_wrong_password_fails(self):
        """A wrong password must return False."""
        hash_val, salt = hash_password("RightPass@1")
        assert verify_password("WrongPass@2", hash_val, salt) is False

    def test_empty_password_returns_false(self):
        """Empty password must return False, not crash."""
        hash_val, salt = hash_password("Something@1")
        assert verify_password("", hash_val, salt) is False

    def test_none_password_returns_false(self):
        """None password must return False."""
        hash_val, salt = hash_password("Something@1")
        assert verify_password(None, hash_val, salt) is False

    def test_empty_hash_returns_false(self):
        """Empty stored hash must return False."""
        assert verify_password("anything", "", "somesalt") is False

    def test_malformed_hash_returns_false(self):
        """A non-bcrypt hash string must return False, not crash."""
        assert verify_password("test", "not_a_bcrypt_hash", "salt") is False

    def test_salt_parameter_is_ignored(self):
        """The salt param is for API compat — bcrypt extracts salt from hash."""
        password = "TestSalt@1"
        hash_val, _ = hash_password(password)
        # Pass a completely different salt — should still verify
        assert verify_password(password, hash_val, "wrong_salt") is True

    def test_case_sensitive_password(self):
        """Password verification must be case-sensitive."""
        hash_val, salt = hash_password("CaseSensitive@1")
        assert verify_password("casesensitive@1", hash_val, salt) is False
        assert verify_password("CASESENSITIVE@1", hash_val, salt) is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. PASSWORD STRENGTH VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestValidatePasswordStrength:
    """Tests for the validate_password_strength function."""

    def test_strong_password_passes(self):
        """A password meeting all criteria must pass."""
        valid, msg = validate_password_strength("Str0ng@Pass")
        assert valid is True

    def test_empty_password_fails(self):
        valid, msg = validate_password_strength("")
        assert valid is False

    def test_short_password_fails(self):
        valid, msg = validate_password_strength("Aa1@")
        assert valid is False
        assert "8 characters" in msg

    def test_no_uppercase_fails(self):
        valid, msg = validate_password_strength("lowercase1@")
        assert valid is False
        assert "uppercase" in msg

    def test_no_lowercase_fails(self):
        valid, msg = validate_password_strength("UPPERCASE1@")
        assert valid is False
        assert "lowercase" in msg

    def test_no_digit_fails(self):
        valid, msg = validate_password_strength("NoDigits@@")
        assert valid is False
        assert "digit" in msg

    def test_no_special_char_fails(self):
        valid, msg = validate_password_strength("NoSpecial1A")
        assert valid is False
        assert "special" in msg


# ─────────────────────────────────────────────────────────────────────────────
# 4. ROLE-BASED ACCESS CONTROL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireRole:
    """Tests for the require_role server-side permission check."""

    def test_admin_allowed_for_admin_role(self):
        user = {"role": "admin", "email": "hr@company.com"}
        assert require_role(user, ["admin"]) is True

    def test_employee_allowed_for_employee_role(self):
        user = {"role": "employee", "email": "emp@company.com"}
        assert require_role(user, ["employee"]) is True

    def test_admin_allowed_when_both_roles_listed(self):
        user = {"role": "admin"}
        assert require_role(user, ["admin", "employee"]) is True

    def test_employee_denied_for_admin_only_action(self):
        user = {"role": "employee"}
        with pytest.raises(PermissionDeniedError, match="Access denied"):
            require_role(user, ["admin"])

    def test_none_user_raises_auth_required(self):
        with pytest.raises(PermissionDeniedError, match="Authentication required"):
            require_role(None, ["admin"])

    def test_empty_dict_user_raises_access_denied(self):
        with pytest.raises(PermissionDeniedError, match="Access denied"):
            require_role({}, ["admin"])

    def test_role_check_is_case_insensitive(self):
        user = {"role": "Admin"}
        assert require_role(user, ["admin"]) is True

        user2 = {"role": "EMPLOYEE"}
        assert require_role(user2, ["employee"]) is True


class TestCheckRole:
    """Tests for the non-raising check_role helper."""

    def test_returns_true_for_valid_role(self):
        assert check_role({"role": "admin"}, ["admin"]) is True

    def test_returns_false_for_invalid_role(self):
        assert check_role({"role": "employee"}, ["admin"]) is False

    def test_returns_false_for_none_user(self):
        assert check_role(None, ["admin"]) is False

    def test_returns_false_for_empty_user(self):
        assert check_role({}, ["admin"]) is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. EMPLOYEE ACCESS OWNERSHIP TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireEmployeeAccess:
    """Tests for the require_employee_access ownership check."""

    def test_admin_can_access_any_employee(self):
        admin = {"role": "admin", "employee_id": None}
        assert require_employee_access(admin, 42) is True

    def test_employee_can_access_own_record(self):
        emp = {"role": "employee", "employee_id": 5}
        assert require_employee_access(emp, 5) is True

    def test_employee_cannot_access_other_record(self):
        emp = {"role": "employee", "employee_id": 5}
        with pytest.raises(PermissionDeniedError, match="Access violation"):
            require_employee_access(emp, 10)

    def test_employee_with_none_id_denied(self):
        emp = {"role": "employee", "employee_id": None}
        with pytest.raises(PermissionDeniedError, match="Access violation"):
            require_employee_access(emp, 1)

    def test_none_user_raises_auth_required(self):
        with pytest.raises(PermissionDeniedError, match="Authentication required"):
            require_employee_access(None, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. SESSION TIMEOUT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionTimeout:
    """Tests for session expiry management."""

    def test_recent_activity_not_expired(self):
        now_iso = datetime.now().isoformat()
        assert is_session_expired(now_iso) is False

    def test_old_activity_is_expired(self):
        old = (datetime.now() - timedelta(minutes=DEFAULT_SESSION_TIMEOUT_MINUTES + 5)).isoformat()
        assert is_session_expired(old) is True

    def test_none_timestamp_is_expired(self):
        assert is_session_expired(None) is True

    def test_empty_string_is_expired(self):
        assert is_session_expired("") is True

    def test_invalid_timestamp_is_expired(self):
        assert is_session_expired("not-a-timestamp") is True

    def test_custom_timeout_shorter(self):
        """A 5-minute timeout with 10-minute-old timestamp should be expired."""
        old = (datetime.now() - timedelta(minutes=10)).isoformat()
        assert is_session_expired(old, timeout_minutes=5) is True

    def test_custom_timeout_longer(self):
        """A 60-minute timeout with 10-minute-old timestamp should NOT be expired."""
        recent = (datetime.now() - timedelta(minutes=10)).isoformat()
        assert is_session_expired(recent, timeout_minutes=60) is False

    def test_get_current_timestamp_iso_format(self):
        ts = get_current_timestamp_iso()
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(ts)
        assert isinstance(parsed, datetime)


# ─────────────────────────────────────────────────────────────────────────────
# 7. DATABASE SEED INTEGRATION TEST
# ─────────────────────────────────────────────────────────────────────────────

class TestSeedAuthAccounts:
    """Tests the seed_auth_accounts_if_empty function from database/db.py."""

    def _create_temp_db(self):
        """Create a temporary in-memory database with the users table schema."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
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
                last_login TIMESTAMP
            )
        """)
        conn.commit()
        return conn

    def test_seeds_admin_when_users_empty(self):
        from database.db import seed_auth_accounts_if_empty
        conn = self._create_temp_db()
        cursor = conn.cursor()

        seed_auth_accounts_if_empty(cursor)
        conn.commit()

        cursor.execute("SELECT * FROM users WHERE email = 'admin@onboardai.com'")
        row = cursor.fetchone()
        assert row is not None, "Default admin account should be seeded"
        assert row["role"] == "admin"
        assert row["username"] == "admin"
        assert row["is_active"] == 1
        assert row["force_password_change"] == 1
        conn.close()

    def test_admin_password_is_hashed_not_plaintext(self):
        from database.db import seed_auth_accounts_if_empty
        conn = self._create_temp_db()
        cursor = conn.cursor()

        seed_auth_accounts_if_empty(cursor)
        conn.commit()

        cursor.execute("SELECT password_hash FROM users WHERE email = 'admin@onboardai.com'")
        row = cursor.fetchone()
        assert row is not None
        stored_hash = row["password_hash"]
        # Must be bcrypt hash, not plaintext
        assert stored_hash.startswith("$2"), "Password hash must be a bcrypt hash"
        assert stored_hash != "Admin@123", "Password must not be stored in plaintext"
        conn.close()

    def test_admin_password_verifies_correctly(self):
        from database.db import seed_auth_accounts_if_empty
        conn = self._create_temp_db()
        cursor = conn.cursor()

        seed_auth_accounts_if_empty(cursor)
        conn.commit()

        cursor.execute("SELECT password_hash, salt FROM users WHERE email = 'admin@onboardai.com'")
        row = cursor.fetchone()
        assert row is not None
        assert verify_password("Admin@123", row["password_hash"], row["salt"]) is True
        assert verify_password("WrongPassword", row["password_hash"], row["salt"]) is False
        conn.close()

    def test_does_not_duplicate_on_second_call(self):
        from database.db import seed_auth_accounts_if_empty
        conn = self._create_temp_db()
        cursor = conn.cursor()

        seed_auth_accounts_if_empty(cursor)
        conn.commit()
        seed_auth_accounts_if_empty(cursor)
        conn.commit()

        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        count = cursor.fetchone()["cnt"]
        assert count == 1, "Should not create duplicate admin accounts"
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
