"""Mercado Pago Pix integration — real payments only."""

import os
import uuid
from datetime import datetime, timedelta

import mercadopago
from sqlalchemy.orm import Session

from server.db.models import PlanType, User

_sdk: mercadopago.SDK | None = None


def _get_sdk() -> mercadopago.SDK:
    global _sdk
    if _sdk is None:
        token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "")
        if not token:
            raise RuntimeError("MERCADO_PAGO_ACCESS_TOKEN not configured")
        _sdk = mercadopago.SDK(token)
    return _sdk


PLAN_PRICES_BRL: dict[str, float] = {
    "pro": 49.90,
    "pro_plus": 149.90,
    "unlimited": 399.90,
}

CREDIT_PACKS: dict[int, float] = {
    50: 29.90,
    200: 99.90,
    500: 199.90,
    1000: 349.90,
}


def create_pix_payment(
    user: User,
    description: str,
    amount_brl: float,
    metadata: dict,
) -> dict:
    """Creates a real Pix payment via Mercado Pago API."""
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
            "type": metadata.get("type", "credits"),
            **metadata,
        },
    }

    result = sdk.payment().create(payment_data, {"X-Idempotency-Key": idempotency})

    if result["status"] not in (200, 201):
        error_msg = result.get("response", {}).get("message", "Unknown error")
        raise RuntimeError(f"Mercado Pago error: {error_msg}")

    response = result["response"]
    pix_data = response.get("point_of_interaction", {}).get("transaction_data", {})

    return {
        "payment_id": response["id"],
        "status": response["status"],
        "amount": response["transaction_amount"],
        "qr_code": pix_data.get("qr_code", ""),
        "qr_code_base64": pix_data.get("qr_code_base64", ""),
        "ticket_url": pix_data.get("ticket_url", ""),
        "expiration": expiration,
    }


def create_plan_payment(user: User, plan_key: str) -> dict:
    if plan_key not in PLAN_PRICES_BRL:
        raise ValueError(f"Plano invalido: {plan_key}")

    price = PLAN_PRICES_BRL[plan_key]
    return create_pix_payment(
        user=user,
        description=f"Nexus Leads - Plano {plan_key.replace('_', ' ').title()}",
        amount_brl=price,
        metadata={"type": "plan", "plan_key": plan_key},
    )


def create_credits_payment(user: User, credit_amount: int) -> dict:
    if credit_amount not in CREDIT_PACKS:
        raise ValueError(f"Pacote de creditos invalido: {credit_amount}")

    price = CREDIT_PACKS[credit_amount]
    return create_pix_payment(
        user=user,
        description=f"Nexus Leads - {credit_amount} creditos",
        amount_brl=price,
        metadata={"type": "credits", "credits": credit_amount},
    )


def process_webhook(payment_id: int, db: Session) -> dict:
    """Called when Mercado Pago confirms payment. Updates user plan/credits."""
    sdk = _get_sdk()
    result = sdk.payment().get(payment_id)

    if result["status"] != 200:
        return {"ok": False, "error": "Payment not found"}

    payment = result["response"]
    if payment["status"] != "approved":
        return {"ok": False, "status": payment["status"]}

    metadata = payment.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        return {"ok": False, "error": "No user_id in metadata"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "error": "User not found"}

    payment_type = metadata.get("type", "")

    if payment_type == "plan":
        plan_key = metadata.get("plan_key", "")
        plan_map = {"pro": PlanType.pro, "pro_plus": PlanType.pro, "unlimited": PlanType.enterprise}
        new_plan = plan_map.get(plan_key)
        if new_plan:
            from server.modules.billing.service import apply_plan_policy
            apply_plan_policy(user, new_plan)
            if plan_key == "pro_plus":
                user.credits_balance += 1000
            elif plan_key == "unlimited":
                user.credits_balance = max(user.credits_balance, 10_000_000)

    elif payment_type == "credits":
        credits = int(metadata.get("credits", 0))
        if credits > 0:
            user.credits_balance += credits

    db.add(user)
    db.commit()

    return {"ok": True, "user_id": user_id, "type": payment_type}
