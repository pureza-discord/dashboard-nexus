"""Unit tests for auth service functions."""

import hashlib
import pytest
from unittest.mock import MagicMock, patch

from server.modules.auth.service import (
    _generate_code,
    _hash_code,
    _normalize_email,
    serialize_user,
)
from server.db.models import PlanType, User


# ---------------------------------------------------------------------------
# Email Normalization Tests
# ---------------------------------------------------------------------------

class TestEmailNormalization:
    def test_lowercase(self):
        assert _normalize_email("Test@Example.COM") == "test@example.com"

    def test_strips_whitespace(self):
        assert _normalize_email("  user@test.com  ") == "user@test.com"

    def test_empty_string(self):
        assert _normalize_email("") == ""


# ---------------------------------------------------------------------------
# Verification Code Tests
# ---------------------------------------------------------------------------

class TestVerificationCode:
    def test_code_is_6_digits(self):
        code = _generate_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_code_hash_deterministic(self):
        h1 = _hash_code("test@example.com", "123456")
        h2 = _hash_code("test@example.com", "123456")
        assert h1 == h2

    def test_code_hash_different_for_different_codes(self):
        h1 = _hash_code("test@example.com", "123456")
        h2 = _hash_code("test@example.com", "654321")
        assert h1 != h2

    def test_code_hash_different_for_different_emails(self):
        h1 = _hash_code("a@example.com", "123456")
        h2 = _hash_code("b@example.com", "123456")
        assert h1 != h2


# ---------------------------------------------------------------------------
# User Serialization Tests
# ---------------------------------------------------------------------------

class TestSerializeUser:
    def test_serialize_user_structure(self):
        user = MagicMock(spec=User)
        user.id = "test-id"
        user.email = "test@example.com"
        user.full_name = "Test User"
        user.plan_type = PlanType.free
        user.is_admin = False
        user.email_verified = True
        user.credits_balance = 150
        user.stripe_customer_id = None
        user.stripe_subscription_id = None
        user.created_at = None
        user.leads_limit_monthly = 150
        user.external_queries_limit_monthly = 5
        user.leads_used_current_month = 0
        user.external_queries_used_current_month = 0
        user.plan_reset_date = None

        result = serialize_user(user)
        assert result["id"] == "test-id"
        assert result["email"] == "test@example.com"
        assert result["plan_type"] == "free"
        assert "billing" in result

    def test_serialize_user_includes_credits(self):
        user = MagicMock(spec=User)
        user.id = "test-id"
        user.email = "test@example.com"
        user.full_name = None
        user.plan_type = PlanType.pro
        user.is_admin = False
        user.email_verified = True
        user.credits_balance = 5000
        user.stripe_customer_id = "cus_123"
        user.stripe_subscription_id = None
        user.created_at = None
        user.leads_limit_monthly = 6000
        user.external_queries_limit_monthly = 0
        user.leads_used_current_month = 0
        user.external_queries_used_current_month = 0
        user.plan_reset_date = None

        result = serialize_user(user)
        assert result["credits_balance"] == 5000
        assert result["stripe_customer_id"] == "cus_123"
