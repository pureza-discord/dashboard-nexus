from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.db.models import PlanType, User


@dataclass(frozen=True)
class PlanPolicy:
    plan: PlanType
    leads_limit_monthly: int | None
    external_queries_limit_monthly: int | None
    allow_csv_export: bool
    allow_multi_user: bool


PLAN_CATALOG: dict[PlanType, PlanPolicy] = {
    PlanType.basic: PlanPolicy(
        plan=PlanType.basic,
        leads_limit_monthly=40,
        external_queries_limit_monthly=2,
        allow_csv_export=False,
        allow_multi_user=False,
    ),
    PlanType.pro: PlanPolicy(
        plan=PlanType.pro,
        leads_limit_monthly=200,
        external_queries_limit_monthly=50,
        allow_csv_export=True,
        allow_multi_user=False,
    ),
    PlanType.enterprise: PlanPolicy(
        plan=PlanType.enterprise,
        leads_limit_monthly=None,
        external_queries_limit_monthly=None,
        allow_csv_export=True,
        allow_multi_user=True,
    ),
}


def get_policy(plan_type: PlanType) -> PlanPolicy:
    return PLAN_CATALOG[plan_type]


def apply_plan_policy(user: User, plan_type: PlanType) -> None:
    policy = get_policy(plan_type)
    user.plan_type = plan_type
    user.leads_limit_monthly = policy.leads_limit_monthly or 0
    user.external_queries_limit_monthly = policy.external_queries_limit_monthly or 0


def _next_month_start(base: date) -> date:
    year = base.year + (1 if base.month == 12 else 0)
    month = 1 if base.month == 12 else base.month + 1
    return date(year, month, 1)


def reset_usage_if_needed(db: Session, user: User) -> None:
    today = date.today()
    if user.plan_reset_date and today < user.plan_reset_date:
        return

    user.leads_used_current_month = 0
    user.external_queries_used_current_month = 0
    user.plan_reset_date = _next_month_start(today)
    db.add(user)


def _plan_remaining_leads(user: User) -> int | None:
    policy = get_policy(user.plan_type)
    if policy.leads_limit_monthly is None:
        return None
    return max(0, policy.leads_limit_monthly - user.leads_used_current_month)


def assert_lead_quota(user: User, requested: int) -> None:
    if requested <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requested lead quantity must be positive")

    if user.is_admin:
        return

    remaining = _plan_remaining_leads(user)
    if remaining is None:
        return

    if requested <= remaining:
        return

    needed_credits = requested - remaining
    if user.credits_balance < needed_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Lead quota exceeded. "
                f"Plan available: {remaining}, credits needed: {needed_credits}, "
                f"credits balance: {user.credits_balance}"
            ),
        )


def consume_leads(db: Session, user: User, amount: int) -> None:
    if amount <= 0 or user.is_admin:
        return

    remaining = _plan_remaining_leads(user)
    if remaining is None:
        db.add(user)
        return

    from_plan = min(remaining, amount)
    user.leads_used_current_month += from_plan

    overflow = amount - from_plan
    if overflow > 0:
        user.credits_balance = max(0, user.credits_balance - overflow)

    db.add(user)


def assert_external_query_quota(user: User, requested: int = 1) -> None:
    if requested <= 0 or user.is_admin:
        return

    policy = get_policy(user.plan_type)
    if policy.external_queries_limit_monthly is None:
        return

    available = max(0, policy.external_queries_limit_monthly - user.external_queries_used_current_month)
    if requested > available:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"External data quota exceeded. Available external queries: {available}",
        )


def consume_external_queries(db: Session, user: User, amount: int = 1) -> None:
    if amount <= 0 or user.is_admin:
        return

    policy = get_policy(user.plan_type)
    if policy.external_queries_limit_monthly is not None:
        user.external_queries_used_current_month += amount
    db.add(user)


def can_export_csv(user: User) -> bool:
    if user.is_admin:
        return True
    return get_policy(user.plan_type).allow_csv_export


def add_credits(db: Session, user: User, amount: int) -> None:
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credits amount must be positive")
    user.credits_balance += amount
    db.add(user)
    db.commit()


def subscribe_plan(db: Session, user: User, plan_type: PlanType) -> None:
    apply_plan_policy(user, plan_type)
    db.add(user)
    db.commit()


def usage_payload(user: User) -> dict:
    policy = get_policy(user.plan_type)
    available_leads = None

    if user.is_admin:
        available_leads = "ilimitado"
    elif policy.leads_limit_monthly is not None:
        available_leads = max(0, policy.leads_limit_monthly - user.leads_used_current_month)

    return {
        "plan_type": user.plan_type.value,
        "is_admin": user.is_admin,
        "leads_limit_mensal": None if user.is_admin else policy.leads_limit_monthly,
        "leads_used_current_month": user.leads_used_current_month,
        "available_leads": available_leads,
        "external_queries_limit_mensal": None if user.is_admin else policy.external_queries_limit_monthly,
        "external_queries_used_current_month": user.external_queries_used_current_month,
        "plan_reset_date": user.plan_reset_date.isoformat() if user.plan_reset_date else None,
        "allow_csv_export": can_export_csv(user),
        "allow_multi_user": True if user.is_admin else policy.allow_multi_user,
        "credits_balance": user.credits_balance,
    }
