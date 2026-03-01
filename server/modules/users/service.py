from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.db.models import PlanType, User
from server.modules.auth.service import serialize_user
from server.modules.billing.service import apply_plan_policy


def update_profile(db: Session, user: User, full_name: str | None) -> dict:
    user.full_name = (full_name or "").strip() or None
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


def update_plan(db: Session, user: User, plan_type: str) -> dict:
    try:
        parsed = PlanType(plan_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan type") from exc

    apply_plan_policy(user, parsed)
    user.plan_type = parsed
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)
