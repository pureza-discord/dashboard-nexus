"""Stripe payment integration for credit purchases and plan subscriptions.

Supports:
- Stripe Checkout sessions for one-time and subscription payments
- Plan upgrades via checkout
- Credit pack purchases via checkout
- Webhook processing for payment confirmation

All payment intents are stored in DB for audit trail.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from server.db.models import (
    PaymentIntent,
    PaymentMethod,
    PaymentStatus,
    PlanType,
    User,
)
from server.modules.billing.service import (
    CREDIT_PACKS,
    add_credits,
    subscribe_plan,
)

logger = logging.getLogger("billing.stripe")


def _get_stripe():
    """Lazy-load and configure the Stripe SDK."""
    try:
        import stripe
    except ImportError:
        raise RuntimeError("stripe SDK not installed. Run: pip install stripe")

    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not configured")

    stripe.api_key = key
    return stripe


# ---------------------------------------------------------------------------
# Plan pricing in BRL cents (Stripe uses cents)
# ---------------------------------------------------------------------------

STRIPE_PLAN_PRICES: dict[str, dict[str, int]] = {
    "go": {"monthly": 3900, "annual": 39000},
    "pro": {"monthly": 8900, "annual": 89000},
    "plus": {"monthly": 17900, "annual": 179000},
    "ilimitado": {"monthly": 44900, "annual": 449000},
}


# ---------------------------------------------------------------------------
# Create Checkout Sessions
# ---------------------------------------------------------------------------

def create_plan_checkout(
    db: Session,
    user: User,
    plan_key: str,
    billing_cycle: str = "monthly",
) -> dict:
    """Create a Stripe Checkout session for plan subscription."""
    stripe = _get_stripe()

    if plan_key not in STRIPE_PLAN_PRICES:
        raise ValueError(f"Invalid plan: {plan_key}. Options: {', '.join(STRIPE_PLAN_PRICES.keys())}")

    cycle_key = "annual" if billing_cycle == "annual" else "monthly"
    amount = STRIPE_PLAN_PRICES[plan_key][cycle_key]
    cycle_label = "Annual" if cycle_key == "annual" else "Monthly"

    success_url = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:5173/account?payment=success")
    cancel_url = os.getenv("STRIPE_CANCEL_URL", "http://localhost:5173/account?payment=cancelled")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": f"NexusCoding - Plan {plan_key.title()} ({cycle_label})",
                },
                "unit_amount": amount,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user.email,
        metadata={
            "user_id": str(user.id),
            "type": "plan",
            "plan_key": plan_key,
            "billing_cycle": cycle_key,
        },
    )

    # Store PaymentIntent in DB
    intent = PaymentIntent(
        user_id=user.id,
        external_payment_id=session.id,
        payment_method=PaymentMethod.credit_card,
        status=PaymentStatus.pending,
        amount_brl=amount / 100.0,
        description=f"Plan {plan_key.title()} ({cycle_label})",
        metadata_json={
            "type": "plan",
            "plan_key": plan_key,
            "billing_cycle": cycle_key,
            "stripe_session_id": session.id,
        },
    )
    db.add(intent)
    db.commit()

    return {
        "session_id": session.id,
        "url": session.url,
        "intent_id": str(intent.id),
    }


def create_credits_checkout(db: Session, user: User, credit_amount: int) -> dict:
    """Create a Stripe Checkout session for credit pack purchase."""
    stripe = _get_stripe()

    if credit_amount not in CREDIT_PACKS:
        valid = ", ".join(str(k) for k in sorted(CREDIT_PACKS.keys()))
        raise ValueError(f"Invalid credit pack: {credit_amount}. Options: {valid}")

    price_brl = CREDIT_PACKS[credit_amount]
    amount_cents = int(price_brl * 100)

    success_url = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:5173/account?payment=success")
    cancel_url = os.getenv("STRIPE_CANCEL_URL", "http://localhost:5173/account?payment=cancelled")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": f"NexusCoding - {credit_amount:,} Extra Credits",
                },
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user.email,
        metadata={
            "user_id": str(user.id),
            "type": "credits",
            "credits": str(credit_amount),
        },
    )

    # Store PaymentIntent in DB
    intent = PaymentIntent(
        user_id=user.id,
        external_payment_id=session.id,
        payment_method=PaymentMethod.credit_card,
        status=PaymentStatus.pending,
        amount_brl=price_brl,
        description=f"{credit_amount:,} extra credits",
        metadata_json={
            "type": "credits",
            "credits": credit_amount,
            "stripe_session_id": session.id,
        },
    )
    db.add(intent)
    db.commit()

    return {
        "session_id": session.id,
        "url": session.url,
        "intent_id": str(intent.id),
    }


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------

def process_stripe_webhook(payload: bytes, sig_header: str, db: Session) -> dict:
    """Process Stripe webhook event. Called on checkout.session.completed."""
    stripe = _get_stripe()

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    if event["type"] != "checkout.session.completed":
        return {"ok": True, "ignored": True, "event_type": event["type"]}

    session = event["data"]["object"]
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")

    if not user_id:
        return {"ok": False, "error": "No user_id in metadata"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "error": "User not found"}

    # Update PaymentIntent
    intent = db.query(PaymentIntent).filter(
        PaymentIntent.external_payment_id == session["id"]
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
            logger.info("[BILLING] Stripe plan upgraded: user=%s plan=%s", user.email, plan_key)

    elif payment_type == "credits":
        credits = int(metadata.get("credits", 0))
        if credits > 0:
            add_credits(db, user, credits, f"Stripe credit purchase ({credits:,} credits)")
            logger.info("[BILLING] Stripe credits purchased: user=%s amount=%d", user.email, credits)

    db.commit()
    return {"ok": True, "user_id": user_id, "type": payment_type}
