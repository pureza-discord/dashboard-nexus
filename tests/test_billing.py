"""Unit tests for the billing service (credit operations).

Tests the credit system math, plan policies, and quota assertions
without hitting external APIs.
"""

import pytest
from unittest.mock import MagicMock
from datetime import date

from server.db.models import PlanType, User
from server.modules.billing.service import (
    CREDIT_COST_AI_MESSAGE,
    CREDIT_COST_LEAD_SEARCH_PER_10,
    PLAN_CATALOG,
    _assert_credits,
    assert_lead_quota,
    assert_source_allowed,
    can_export_csv,
    deduct_credits,
    get_policy,
    plans_list,
    usage_payload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_user(plan: PlanType = PlanType.free, credits: int = 150, is_admin: bool = False) -> User:
    """Create a mock User with typical defaults."""
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.plan_type = plan
    user.credits_balance = credits
    user.is_admin = is_admin
    user.leads_used_current_month = 0
    user.external_queries_used_current_month = 0
    user.plan_reset_date = date(2026, 4, 1)
    user.stripe_customer_id = None
    user.stripe_subscription_id = None
    return user


def _make_db():
    """Create a mock DB session."""
    db = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Plan Policy Tests
# ---------------------------------------------------------------------------

class TestPlanPolicy:
    def test_free_plan_has_150_credits(self):
        policy = get_policy(PlanType.free)
        assert policy.monthly_credits == 150
        assert policy.display_name == "Free"

    def test_ilimitado_plan_is_unlimited(self):
        policy = get_policy(PlanType.ilimitado)
        assert policy.monthly_credits is None
        assert policy.allow_white_label is True

    def test_all_plans_exist(self):
        for plan_type in [PlanType.free, PlanType.go, PlanType.pro, PlanType.plus, PlanType.ilimitado]:
            policy = get_policy(plan_type)
            assert policy.plan == plan_type

    def test_legacy_basic_maps_to_free(self):
        policy = get_policy(PlanType.basic)
        assert policy.monthly_credits == 150

    def test_legacy_enterprise_maps_to_ilimitado(self):
        policy = get_policy(PlanType.enterprise)
        assert policy.monthly_credits is None

    def test_plans_list_returns_5_plans(self):
        plans = plans_list()
        assert len(plans) == 5
        plan_types = {p["plan_type"] for p in plans}
        assert plan_types == {"free", "go", "pro", "plus", "ilimitado"}

    def test_pro_is_most_popular(self):
        plans = plans_list()
        pro = next(p for p in plans if p["plan_type"] == "pro")
        assert pro["is_most_popular"] is True


# ---------------------------------------------------------------------------
# Credit Operations Tests
# ---------------------------------------------------------------------------

class TestCreditOperations:
    def test_assert_credits_passes_with_enough(self):
        user = _make_user(credits=100)
        # Should not raise
        _assert_credits(user, 50, "test")

    def test_assert_credits_fails_with_insufficient(self):
        user = _make_user(credits=10)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _assert_credits(user, 50, "test")
        assert exc_info.value.status_code == 402

    def test_assert_credits_passes_for_admin(self):
        user = _make_user(credits=0, is_admin=True)
        # Should not raise even with 0 credits
        _assert_credits(user, 1000, "test")

    def test_assert_credits_passes_for_unlimited_plan(self):
        user = _make_user(plan=PlanType.ilimitado, credits=0)
        # Should not raise for unlimited plan
        _assert_credits(user, 1000, "test")

    def test_deduct_credits_decreases_balance(self):
        user = _make_user(credits=100)
        db = _make_db()
        deduct_credits(db, user, 30, "test deduction")
        assert user.credits_balance == 70

    def test_deduct_credits_skips_admin(self):
        user = _make_user(credits=100, is_admin=True)
        db = _make_db()
        deduct_credits(db, user, 30, "test deduction")
        assert user.credits_balance == 100  # Unchanged

    def test_deduct_credits_skips_unlimited_plan(self):
        user = _make_user(plan=PlanType.ilimitado, credits=100)
        db = _make_db()
        deduct_credits(db, user, 30, "test deduction")
        assert user.credits_balance == 100  # Unchanged


# ---------------------------------------------------------------------------
# Quota Assertion Tests
# ---------------------------------------------------------------------------

class TestQuotaAssertions:
    def test_assert_lead_quota_passes(self):
        user = _make_user(credits=200)
        # 10 leads = 1 batch * 15 credits = 15 credits
        assert_lead_quota(user, 10)  # Should not raise

    def test_assert_lead_quota_fails_over_plan_limit(self):
        user = _make_user(plan=PlanType.free, credits=200)
        # Free plan max is 10 leads per search
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            assert_lead_quota(user, 50)
        assert exc_info.value.status_code == 403

    def test_assert_source_workana_blocked_on_free(self):
        user = _make_user(plan=PlanType.free)
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            assert_source_allowed(user, "workana")

    def test_assert_source_workana_allowed_on_go(self):
        user = _make_user(plan=PlanType.go)
        assert_source_allowed(user, "workana")  # Should not raise

    def test_assert_source_linkedin_blocked_on_go(self):
        user = _make_user(plan=PlanType.go)
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            assert_source_allowed(user, "linkedin")

    def test_assert_source_linkedin_allowed_on_pro(self):
        user = _make_user(plan=PlanType.pro)
        assert_source_allowed(user, "linkedin")  # Should not raise


# ---------------------------------------------------------------------------
# Feature Checks
# ---------------------------------------------------------------------------

class TestFeatureChecks:
    def test_csv_export_blocked_on_free(self):
        user = _make_user(plan=PlanType.free)
        assert can_export_csv(user) is False

    def test_csv_export_allowed_on_go(self):
        user = _make_user(plan=PlanType.go)
        assert can_export_csv(user) is True

    def test_csv_export_always_allowed_for_admin(self):
        user = _make_user(plan=PlanType.free, is_admin=True)
        assert can_export_csv(user) is True


# ---------------------------------------------------------------------------
# Usage Payload Tests
# ---------------------------------------------------------------------------

class TestUsagePayload:
    def test_usage_payload_structure(self):
        user = _make_user(credits=100)
        payload = usage_payload(user)
        assert "plan_type" in payload
        assert "credits_balance" in payload
        assert "costs" in payload
        assert payload["credits_balance"] == 100

    def test_usage_payload_unlimited(self):
        user = _make_user(plan=PlanType.ilimitado, credits=5000)
        payload = usage_payload(user)
        assert payload["is_unlimited"] is True
        assert payload["available_credits"] == "ilimitado"
