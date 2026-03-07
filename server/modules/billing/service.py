"""Billing service with Cursor-AI-style credit system.

5 tiers: Free / Go / Pro / Plus / Ilimitado
Credit consumption rules enforce strict per-action costs.
All mutations are atomic and logged in credit_transactions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.db.models import (
    CreditTransaction,
    CreditTransactionType,
    PlanType,
    User,
)

logger = logging.getLogger("billing")


# ---------------------------------------------------------------------------
# Plan Catalog
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanPolicy:
    plan: PlanType
    display_name: str
    monthly_credits: int | None          # None = unlimited
    max_leads_per_search: int | None     # None = no cap
    price_monthly_brl: float
    price_annual_brl: float
    allow_csv_export: bool
    allow_workana: bool
    allow_linkedin: bool
    allow_facebook: bool
    allow_api_access: bool
    allow_white_label: bool
    priority_scraping: bool


PLAN_CATALOG: dict[PlanType, PlanPolicy] = {
    PlanType.free: PlanPolicy(
        plan=PlanType.free,
        display_name="Free",
        monthly_credits=150,
        max_leads_per_search=10,
        price_monthly_brl=0.0,
        price_annual_brl=0.0,
        allow_csv_export=False,
        allow_workana=False,
        allow_linkedin=False,
        allow_facebook=False,
        allow_api_access=False,
        allow_white_label=False,
        priority_scraping=False,
    ),
    PlanType.go: PlanPolicy(
        plan=PlanType.go,
        display_name="Go",
        monthly_credits=1_500,
        max_leads_per_search=50,
        price_monthly_brl=39.0,
        price_annual_brl=390.0,
        allow_csv_export=True,
        allow_workana=True,
        allow_linkedin=False,
        allow_facebook=False,
        allow_api_access=False,
        allow_white_label=False,
        priority_scraping=False,
    ),
    PlanType.pro: PlanPolicy(
        plan=PlanType.pro,
        display_name="Pro",
        monthly_credits=6_000,
        max_leads_per_search=200,
        price_monthly_brl=89.0,
        price_annual_brl=890.0,
        allow_csv_export=True,
        allow_workana=True,
        allow_linkedin=True,
        allow_facebook=True,
        allow_api_access=False,
        allow_white_label=False,
        priority_scraping=True,
    ),
    PlanType.plus: PlanPolicy(
        plan=PlanType.plus,
        display_name="Plus",
        monthly_credits=20_000,
        max_leads_per_search=None,
        price_monthly_brl=179.0,
        price_annual_brl=1_790.0,
        allow_csv_export=True,
        allow_workana=True,
        allow_linkedin=True,
        allow_facebook=True,
        allow_api_access=True,
        allow_white_label=False,
        priority_scraping=True,
    ),
    PlanType.ilimitado: PlanPolicy(
        plan=PlanType.ilimitado,
        display_name="Ilimitado",
        monthly_credits=None,
        max_leads_per_search=None,
        price_monthly_brl=449.0,
        price_annual_brl=4_490.0,
        allow_csv_export=True,
        allow_workana=True,
        allow_linkedin=True,
        allow_facebook=True,
        allow_api_access=True,
        allow_white_label=True,
        priority_scraping=True,
    ),
}

# Legacy alias mappings
PLAN_CATALOG[PlanType.basic] = PLAN_CATALOG[PlanType.free]
PLAN_CATALOG[PlanType.enterprise] = PLAN_CATALOG[PlanType.ilimitado]


# ---------------------------------------------------------------------------
# Credit Packs (one-time purchases, never expire)
# ---------------------------------------------------------------------------

CREDIT_PACKS: dict[int, float] = {
    500: 29.0,
    2_500: 99.0,
    10_000: 349.0,
}


# ---------------------------------------------------------------------------
# Credit Costs (per action)
# ---------------------------------------------------------------------------

CREDIT_COST_AI_MESSAGE = 5
CREDIT_COST_LEAD_SEARCH_PER_10 = 15
CREDIT_COST_WORKANA_SEARCH = 10
CREDIT_COST_CSV_EXPORT = 5
CREDIT_COST_DEEP_SCRAPE_PER_10 = 25  # LinkedIn / Facebook


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------

def get_policy(plan_type: PlanType) -> PlanPolicy:
    return PLAN_CATALOG.get(plan_type, PLAN_CATALOG[PlanType.free])


def apply_plan_policy(user: User, plan_type: PlanType) -> None:
    policy = get_policy(plan_type)
    user.plan_type = plan_type
    user.leads_limit_monthly = policy.monthly_credits or 0
    user.external_queries_limit_monthly = 0  # Legacy field


# ---------------------------------------------------------------------------
# Credit balance operations (all atomic, all logged)
# ---------------------------------------------------------------------------

def _log_transaction(
    db: Session,
    user: User,
    *,
    amount: int,
    tx_type: CreditTransactionType,
    description: str,
    task_id: str | None = None,
) -> CreditTransaction:
    """Create a credit transaction log entry. Must be called inside a commit boundary."""
    tx = CreditTransaction(
        user_id=user.id,
        amount=amount,
        type=tx_type,
        balance_after=user.credits_balance,
        description=description[:500],
        related_task_id=task_id,
    )
    db.add(tx)
    return tx


def _assert_credits(user: User, required: int, action_name: str) -> None:
    """Raise 402 if user doesn't have enough credits for the action."""
    if user.is_admin:
        return
    policy = get_policy(user.plan_type)
    if policy.monthly_credits is None:  # Unlimited plan
        return
    if user.credits_balance < required:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "insufficient_credits",
                "message": f"Você precisa de {required} créditos para {action_name}. Saldo atual: {user.credits_balance}.",
                "required": required,
                "balance": user.credits_balance,
                "action": action_name,
            },
        )


def deduct_credits(
    db: Session,
    user: User,
    amount: int,
    description: str,
    task_id: str | None = None,
) -> None:
    """Deduct credits from user balance. Raises 402 if insufficient."""
    if amount <= 0 or user.is_admin:
        return
    policy = get_policy(user.plan_type)
    if policy.monthly_credits is None:
        return

    _assert_credits(user, amount, description)
    user.credits_balance = max(0, user.credits_balance - amount)
    db.add(user)
    _log_transaction(db, user, amount=-amount, tx_type=CreditTransactionType.usage,
                     description=description, task_id=task_id)


def add_credits(db: Session, user: User, amount: int, description: str = "Credit purchase") -> None:
    """Add credits to user balance (purchase or admin adjustment)."""
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credits amount must be positive")
    user.credits_balance += amount
    db.add(user)
    _log_transaction(db, user, amount=amount, tx_type=CreditTransactionType.purchase,
                     description=description)
    db.commit()


def reset_monthly_credits(db: Session, user: User) -> None:
    """Reset credits to plan monthly allowance. Called on period reset."""
    policy = get_policy(user.plan_type)
    if policy.monthly_credits is None:
        return
    # Monthly credits replace (not add to) the plan portion, but extra purchased credits are preserved
    # We set balance = monthly_credits (purchased extras are tracked separately in credit_transactions)
    old_balance = user.credits_balance
    user.credits_balance = policy.monthly_credits
    user.leads_used_current_month = 0
    user.external_queries_used_current_month = 0
    user.plan_reset_date = _next_month_start(date.today())
    db.add(user)
    _log_transaction(db, user, amount=policy.monthly_credits - old_balance,
                     tx_type=CreditTransactionType.monthly_reset,
                     description=f"Monthly reset ({policy.display_name} plan: {policy.monthly_credits} credits)")


# ---------------------------------------------------------------------------
# Specific credit consumption functions
# ---------------------------------------------------------------------------

def consume_ai_message(db: Session, user: User) -> None:
    """Charge for 1 AI conversation message (5 credits)."""
    deduct_credits(db, user, CREDIT_COST_AI_MESSAGE, "AI message")


def consume_lead_search(db: Session, user: User, leads_returned: int, task_id: str | None = None) -> None:
    """Charge for lead search: 15 credits per 10 leads."""
    if leads_returned <= 0:
        return
    batches = max(1, (leads_returned + 9) // 10)
    cost = batches * CREDIT_COST_LEAD_SEARCH_PER_10
    deduct_credits(db, user, cost, f"Lead search ({leads_returned} leads)", task_id=task_id)


def consume_deep_scrape(db: Session, user: User, leads_returned: int, source: str, task_id: str | None = None) -> None:
    """Charge for LinkedIn/Facebook deep scrape: 25 credits per 10 leads."""
    if leads_returned <= 0:
        return
    batches = max(1, (leads_returned + 9) // 10)
    cost = batches * CREDIT_COST_DEEP_SCRAPE_PER_10
    deduct_credits(db, user, cost, f"{source} deep scrape ({leads_returned} leads)", task_id=task_id)


def consume_workana_search(db: Session, user: User, task_id: str | None = None) -> None:
    """Charge for Workana search (10 credits)."""
    deduct_credits(db, user, CREDIT_COST_WORKANA_SEARCH, "Workana search", task_id=task_id)


def consume_csv_export(db: Session, user: User) -> None:
    """Charge for CSV export (5 credits)."""
    deduct_credits(db, user, CREDIT_COST_CSV_EXPORT, "CSV export")


# ---------------------------------------------------------------------------
# Quota assertions (used before starting expensive operations)
# ---------------------------------------------------------------------------

def assert_lead_quota(user: User, requested: int) -> None:
    """Assert user has enough credits for a lead search."""
    if requested <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requested quantity must be positive")
    if user.is_admin:
        return
    policy = get_policy(user.plan_type)
    if policy.monthly_credits is None:
        return
    # Check max leads per search
    if policy.max_leads_per_search is not None and requested > policy.max_leads_per_search:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Seu plano {policy.display_name} permite no máximo {policy.max_leads_per_search} leads por busca. "
                f"Faça upgrade para buscar mais."
            ),
        )
    batches = max(1, (requested + 9) // 10)
    cost = batches * CREDIT_COST_LEAD_SEARCH_PER_10
    _assert_credits(user, cost, f"search for {requested} leads")


def assert_external_query_quota(user: User, requested: int = 1) -> None:
    """Assert user has enough credits for external queries (market analysis)."""
    if requested <= 0 or user.is_admin:
        return
    cost = requested * CREDIT_COST_WORKANA_SEARCH
    _assert_credits(user, cost, "external query")


def assert_source_allowed(user: User, source: str) -> None:
    """Assert user's plan allows the requested scraping source."""
    policy = get_policy(user.plan_type)
    source_lower = source.lower()
    if source_lower == "workana" and not policy.allow_workana:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Workana search requires Go plan or higher. Upgrade to access.")
    if source_lower == "linkedin" and not policy.allow_linkedin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="LinkedIn search requires Pro plan or higher. Upgrade to access.")
    if source_lower == "facebook" and not policy.allow_facebook:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Facebook search requires Pro plan or higher. Upgrade to access.")


# ---------------------------------------------------------------------------
# Legacy compatibility (consume_leads / consume_external_queries)
# ---------------------------------------------------------------------------

def consume_leads(db: Session, user: User, amount: int) -> None:
    """Legacy wrapper for backward compatibility with tasks.py."""
    consume_lead_search(db, user, amount)


def consume_external_queries(db: Session, user: User, amount: int = 1) -> None:
    """Legacy wrapper for backward compatibility with tasks.py."""
    if amount <= 0 or user.is_admin:
        return
    cost = amount * CREDIT_COST_WORKANA_SEARCH
    deduct_credits(db, user, cost, f"External query ({amount})")


# ---------------------------------------------------------------------------
# Feature checks
# ---------------------------------------------------------------------------

def can_export_csv(user: User) -> bool:
    if user.is_admin:
        return True
    return get_policy(user.plan_type).allow_csv_export


def subscribe_plan(db: Session, user: User, plan_type: PlanType) -> None:
    """Change user's plan and reset credits to new plan level."""
    policy = get_policy(plan_type)
    user.plan_type = plan_type
    user.leads_limit_monthly = policy.monthly_credits or 0
    if policy.monthly_credits is not None:
        user.credits_balance = max(user.credits_balance, policy.monthly_credits)
    db.add(user)
    _log_transaction(db, user, amount=0, tx_type=CreditTransactionType.monthly_reset,
                     description=f"Plan changed to {policy.display_name}")
    db.commit()


# ---------------------------------------------------------------------------
# Usage reset
# ---------------------------------------------------------------------------

def _next_month_start(base: date) -> date:
    year = base.year + (1 if base.month == 12 else 0)
    month = 1 if base.month == 12 else base.month + 1
    return date(year, month, 1)


def reset_usage_if_needed(db: Session, user: User) -> None:
    today = date.today()
    if user.plan_reset_date and today < user.plan_reset_date:
        return
    reset_monthly_credits(db, user)


# ---------------------------------------------------------------------------
# Usage payload (for API responses / dashboard)
# ---------------------------------------------------------------------------

def usage_payload(user: User) -> dict:
    policy = get_policy(user.plan_type)
    monthly = policy.monthly_credits
    is_unlimited = monthly is None

    if user.is_admin:
        available = "ilimitado"
    elif is_unlimited:
        available = "ilimitado"
    else:
        available = user.credits_balance

    days_until_reset = 0
    if user.plan_reset_date:
        days_until_reset = max(0, (user.plan_reset_date - date.today()).days)

    return {
        "plan_type": user.plan_type.value,
        "plan_display_name": policy.display_name,
        "is_admin": user.is_admin,
        "is_unlimited": is_unlimited or user.is_admin,
        "credits_balance": user.credits_balance,
        "monthly_credits": monthly,
        "available_credits": available,
        "max_leads_per_search": policy.max_leads_per_search,
        "plan_reset_date": user.plan_reset_date.isoformat() if user.plan_reset_date else None,
        "days_until_reset": days_until_reset,
        "allow_csv_export": can_export_csv(user),
        "allow_workana": policy.allow_workana,
        "allow_linkedin": policy.allow_linkedin,
        "allow_facebook": policy.allow_facebook,
        "allow_api_access": policy.allow_api_access,
        "priority_scraping": policy.priority_scraping,
        # Credit costs (for frontend display)
        "costs": {
            "ai_message": CREDIT_COST_AI_MESSAGE,
            "lead_search_per_10": CREDIT_COST_LEAD_SEARCH_PER_10,
            "workana_search": CREDIT_COST_WORKANA_SEARCH,
            "csv_export": CREDIT_COST_CSV_EXPORT,
            "deep_scrape_per_10": CREDIT_COST_DEEP_SCRAPE_PER_10,
        },
    }


# ---------------------------------------------------------------------------
# Plans list (for pricing page / frontend)
# ---------------------------------------------------------------------------

def plans_list() -> list[dict]:
    """Return all plans with pricing for the frontend pricing table."""
    result = []
    for pt in [PlanType.free, PlanType.go, PlanType.pro, PlanType.plus, PlanType.ilimitado]:
        p = PLAN_CATALOG[pt]
        result.append({
            "plan_type": pt.value,
            "display_name": p.display_name,
            "monthly_credits": p.monthly_credits,
            "max_leads_per_search": p.max_leads_per_search,
            "price_monthly_brl": p.price_monthly_brl,
            "price_annual_brl": p.price_annual_brl,
            "annual_discount_pct": round((1 - p.price_annual_brl / (p.price_monthly_brl * 12)) * 100) if p.price_monthly_brl > 0 else 0,
            "allow_csv_export": p.allow_csv_export,
            "allow_workana": p.allow_workana,
            "allow_linkedin": p.allow_linkedin,
            "allow_facebook": p.allow_facebook,
            "allow_api_access": p.allow_api_access,
            "allow_white_label": p.allow_white_label,
            "priority_scraping": p.priority_scraping,
            "is_most_popular": pt == PlanType.pro,
        })
    return result
