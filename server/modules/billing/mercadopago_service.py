"""Mercado Pago PIX + Card integration for credit purchases and plan subscriptions.

Supports:
- PIX payments (instant, QR code + copia-e-cola)
- Plan subscriptions (monthly/annual)
- Credit pack purchases
- Webhook processing for payment confirmation

All payment intents are stored in DB for audit trail.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from server.db.models import (
    BillingCycle,
    PaymentIntent,
    PaymentMethod,
    PaymentStatus,
    PlanType,
    User,
)
from server.modules.billing.service import (
    CREDIT_PACKS,
    add_credits,
    get_policy,
    plans_list,
    subscribe_plan,
)

logger = logging.getLogger("billing.mercadopago")

_sdk = None


def _get_sdk():
    global _sdk
    if _sdk is None:
        try:
            import mercadopago
        except ImportError:
            raise RuntimeError("mercadopago SDK not installed. Run: pip install mercadopago")
        token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "")
        if not token:
            raise RuntimeError("MERCADO_PAGO_ACCESS_TOKEN not configured")
        _sdk = mercadopago.SDK(token)
    return _sdk


# ---------------------------------------------------------------------------
# Plan pricing (matches billing/service.py catalog)
# ---------------------------------------------------------------------------

PLAN_PRICES_BRL: dict[str, dict[str, float]] = {
    "go": {"monthly": 39.0, "annual": 390.0},
    "pro": {"monthly": 89.0, "annual": 890.0},
    "plus": {"monthly": 179.0, "annual": 1790.0},
    "ilimitado": {"monthly": 449.0, "annual": 4490.0},
}


# ---------------------------------------------------------------------------
# Create PIX payment
# ---------------------------------------------------------------------------

def create_pix_payment(
    db: Session,
    user: User,
    description: str,
    amount_brl: float,
    metadata: dict,
) -> dict:
    """Creates a real Pix payment via Mercado Pago API and stores PaymentIntent."""
    sdk = _get_sdk()

    idempotency = str(uuid.uuid4())
    expiration = (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"

    payment_data = {
        "transaction_amount": round(amount_brl, 2),
        "description": description,
        "payment_method_id": "pix",
        "payer": {
            "email": user.email,
        },
        "date_of_expiration": expiration,
        "external_reference": f"user_{user.id}_{idempotency[:8]}",
        "metadata": {
            "user_id": str(user.id),
            **metadata,
        },
    }

    result = sdk.payment().create(payment_data, {"X-Idempotency-Key": idempotency})

    if result["status"] not in (200, 201):
        error_msg = result.get("response", {}).get("message", "Unknown error")
        raise RuntimeError(f"Mercado Pago error: {error_msg}")

    response = result["response"]
    pix_data = response.get("point_of_interaction", {}).get("transaction_data", {})

    # Store PaymentIntent in DB
    intent = PaymentIntent(
        user_id=user.id,
        external_payment_id=str(response["id"]),
        payment_method=PaymentMethod.pix,
        status=PaymentStatus.pending,
        amount_brl=amount_brl,
        description=description,
        metadata_json=metadata,
        pix_qr_code=pix_data.get("qr_code", ""),
        pix_qr_code_base64=pix_data.get("qr_code_base64", ""),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)

    return {
        "payment_id": response["id"],
        "intent_id": str(intent.id),
        "status": response["status"],
        "amount": response["transaction_amount"],
        "qr_code": pix_data.get("qr_code", ""),
        "qr_code_base64": pix_data.get("qr_code_base64", ""),
        "ticket_url": pix_data.get("ticket_url", ""),
        "expiration": expiration,
    }


# ---------------------------------------------------------------------------
# Create plan + credit payments
# ---------------------------------------------------------------------------

def create_plan_payment(
    db: Session,
    user: User,
    plan_key: str,
    billing_cycle: str = "monthly",
) -> dict:
    """Create PIX payment for plan subscription."""
    if plan_key not in PLAN_PRICES_BRL:
        raise ValueError(f"Plano inválido: {plan_key}. Opções: {', '.join(PLAN_PRICES_BRL.keys())}")

    cycle_key = "annual" if billing_cycle == "annual" else "monthly"
    price = PLAN_PRICES_BRL[plan_key][cycle_key]
    cycle_label = "anual" if cycle_key == "annual" else "mensal"

    return create_pix_payment(
        db=db,
        user=user,
        description=f"LeadAI Global - Plano {plan_key.title()} ({cycle_label})",
        amount_brl=price,
        metadata={
            "type": "plan",
            "plan_key": plan_key,
            "billing_cycle": cycle_key,
        },
    )


def create_credits_payment(db: Session, user: User, credit_amount: int) -> dict:
    """Create PIX payment for credit pack purchase."""
    if credit_amount not in CREDIT_PACKS:
        valid = ", ".join(str(k) for k in sorted(CREDIT_PACKS.keys()))
        raise ValueError(f"Pacote de créditos inválido: {credit_amount}. Opções: {valid}")

    price = CREDIT_PACKS[credit_amount]
    return create_pix_payment(
        db=db,
        user=user,
        description=f"LeadAI Global - {credit_amount:,} créditos extras",
        amount_brl=price,
        metadata={"type": "credits", "credits": credit_amount},
    )


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------

def process_webhook(payment_id: int, db: Session) -> dict:
    """Called when Mercado Pago confirms payment. Updates user plan/credits atomically."""
    sdk = _get_sdk()
    result = sdk.payment().get(payment_id)

    if result["status"] != 200:
        return {"ok": False, "error": "Payment not found"}

    payment = result["response"]
    if payment["status"] != "approved":
        # Update PaymentIntent status
        intent = db.query(PaymentIntent).filter(
            PaymentIntent.external_payment_id == str(payment_id)
        ).first()
        if intent:
            intent.status = PaymentStatus.failed
            intent.updated_at = datetime.utcnow()
            db.add(intent)
            db.commit()
        return {"ok": False, "status": payment["status"]}

    metadata = payment.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        return {"ok": False, "error": "No user_id in metadata"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "error": "User not found"}

    # Update PaymentIntent
    intent = db.query(PaymentIntent).filter(
        PaymentIntent.external_payment_id == str(payment_id)
    ).first()
    if intent:
        intent.status = PaymentStatus.paid
        intent.paid_at = datetime.utcnow()
        intent.updated_at = datetime.utcnow()
        db.add(intent)

    payment_type = metadata.get("type", "")

    if payment_type == "plan":
        plan_key = metadata.get("plan_key", "")
        plan_map = {
            "go": PlanType.go,
            "pro": PlanType.pro,
            "plus": PlanType.plus,
            "ilimitado": PlanType.ilimitado,
        }
        new_plan = plan_map.get(plan_key)
        if new_plan:
            subscribe_plan(db, user, new_plan)
            logger.info("[BILLING] Plan upgraded: user=%s plan=%s", user.email, plan_key)

    elif payment_type == "credits":
        credits = int(metadata.get("credits", 0))
        if credits > 0:
            add_credits(db, user, credits, f"Credit pack purchase ({credits:,} credits)")
            logger.info("[BILLING] Credits purchased: user=%s amount=%d", user.email, credits)

    db.commit()
    return {"ok": True, "user_id": user_id, "type": payment_type}
