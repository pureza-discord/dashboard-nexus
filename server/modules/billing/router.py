"""Billing API endpoints.

Endpoints:
- GET  /api/billing/usage          — Current user's credit usage
- GET  /api/billing/plans          — All plans with pricing
- GET  /api/billing/credit-packs   — Available credit packs
- GET  /api/billing/transactions   — Credit transaction history
- POST /api/billing/pix/plan       — Create PIX payment for plan upgrade
- POST /api/billing/pix/credits    — Create PIX payment for credit pack
- POST /api/billing/webhook/mercadopago — Webhook for payment confirmation
- POST /api/billing/admin/credits  — Admin: adjust user credits
- POST /api/billing/admin/plan     — Admin: change user plan
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import CreditTransaction, CreditTransactionType, PlanType, User
from server.modules.billing.mercadopago_service import (
    CREDIT_PACKS,
    PLAN_PRICES_BRL,
    create_credits_payment,
    create_plan_payment,
    process_webhook,
)
from server.modules.billing.schemas import (
    AdminCreditAdjustment,
    AdminPlanChange,
    CreditsPaymentRequest,
    PlanPaymentRequest,
)
from server.modules.billing.service import (
    CREDIT_COST_AI_MESSAGE,
    CREDIT_COST_CSV_EXPORT,
    CREDIT_COST_DEEP_SCRAPE_PER_10,
    CREDIT_COST_LEAD_SEARCH_PER_10,
    CREDIT_COST_WORKANA_SEARCH,
    add_credits,
    plans_list,
    subscribe_plan,
    usage_payload,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/usage")
def get_usage(current_user: User = Depends(get_current_user)):
    return usage_payload(current_user)


@router.get("/plans")
def get_plans():
    return {
        "plans": plans_list(),
        "credit_packs": [
            {"credits": k, "price_brl": v}
            for k, v in sorted(CREDIT_PACKS.items())
        ],
        "credit_costs": {
            "ai_message": CREDIT_COST_AI_MESSAGE,
            "lead_search_per_10": CREDIT_COST_LEAD_SEARCH_PER_10,
            "workana_search": CREDIT_COST_WORKANA_SEARCH,
            "csv_export": CREDIT_COST_CSV_EXPORT,
            "deep_scrape_per_10": CREDIT_COST_DEEP_SCRAPE_PER_10,
        },
    }


@router.get("/credit-packs")
def get_credit_packs():
    return [
        {"credits": k, "price_brl": v}
        for k, v in sorted(CREDIT_PACKS.items())
    ]


@router.get("/transactions")
def get_transactions(
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return last N credit transactions for the current user."""
    limit = max(1, min(limit, 200))
    rows = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(tx.id),
            "amount": tx.amount,
            "type": tx.type.value,
            "balance_after": tx.balance_after,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx in rows
    ]


@router.post("/pix/plan")
def pix_plan(
    payload: PlanPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = create_plan_payment(db, current_user, payload.plan_key, payload.billing_cycle)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/pix/credits")
def pix_credits(
    payload: CreditsPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = create_credits_payment(db, current_user, payload.credits)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/webhook/mercadopago")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives payment confirmation from Mercado Pago. Public endpoint (no auth)."""
    body = await request.json()

    if body.get("type") != "payment" and body.get("action") != "payment.updated":
        return {"ok": True, "ignored": True}

    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        return {"ok": False, "error": "No payment id"}

    result = process_webhook(int(payment_id), db)
    return result


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.post("/admin/credits")
def admin_adjust_credits(
    payload: AdminCreditAdjustment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only: Add or remove credits from any user."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.amount > 0:
        add_credits(db, user, payload.amount, f"Admin: {payload.description}")
    elif payload.amount < 0:
        user.credits_balance = max(0, user.credits_balance + payload.amount)
        db.add(user)
        tx = CreditTransaction(
            user_id=user.id,
            amount=payload.amount,
            type=CreditTransactionType.admin_adjustment,
            balance_after=user.credits_balance,
            description=f"Admin: {payload.description}",
        )
        db.add(tx)
        db.commit()

    return {
        "ok": True,
        "user_id": payload.user_id,
        "new_balance": user.credits_balance,
        "adjustment": payload.amount,
    }


@router.post("/admin/plan")
def admin_change_plan(
    payload: AdminPlanChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only: Change a user's plan."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_plan = PlanType(payload.plan_type)
    subscribe_plan(db, user, new_plan)

    return {
        "ok": True,
        "user_id": payload.user_id,
        "new_plan": new_plan.value,
        "new_balance": user.credits_balance,
    }
