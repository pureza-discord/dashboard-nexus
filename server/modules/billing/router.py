from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.db.models import User
from server.modules.billing.mercadopago_service import (
    CREDIT_PACKS,
    PLAN_PRICES_BRL,
    create_credits_payment,
    create_plan_payment,
    process_webhook,
)
from server.modules.billing.service import PLAN_CATALOG, usage_payload

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PlanPaymentRequest(BaseModel):
    plan_key: str


class CreditsPaymentRequest(BaseModel):
    credits: int


@router.get("/usage")
def get_usage(current_user: User = Depends(get_current_user)):
    return usage_payload(current_user)


@router.get("/plans")
def get_plans():
    return {
        "plans": [
            {
                "plan_type": policy.plan.value,
                "leads_limit_mensal": policy.leads_limit_monthly,
                "external_queries_limit_mensal": policy.external_queries_limit_monthly,
                "allow_csv_export": policy.allow_csv_export,
            }
            for policy in PLAN_CATALOG.values()
        ],
        "prices": PLAN_PRICES_BRL,
        "credit_packs": CREDIT_PACKS,
    }


@router.post("/pix/plan")
def create_plan_pix(
    payload: PlanPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = create_plan_payment(current_user, payload.plan_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/pix/credits")
def create_credits_pix(
    payload: CreditsPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = create_credits_payment(current_user, payload.credits)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/webhook/mercadopago")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives payment confirmation from Mercado Pago. No auth required (public endpoint)."""
    body = await request.json()

    if body.get("type") != "payment" and body.get("action") != "payment.updated":
        return {"ok": True, "ignored": True}

    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        return {"ok": False, "error": "No payment id"}

    result = process_webhook(int(payment_id), db)
    return result
