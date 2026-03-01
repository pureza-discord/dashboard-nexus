import hashlib
import os
import random
from datetime import datetime, timedelta

import resend
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.core.security import create_access_token, hash_password, verify_password
from server.core.settings import get_settings
from server.db.models import EmailVerificationCode, PlanType, User, VerificationPurpose
from server.modules.billing.service import apply_plan_policy, usage_payload

settings = get_settings()
resend.api_key = os.getenv("RESEND_API_KEY", "")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _now() -> datetime:
    return datetime.utcnow()


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _hash_code(email: str, code: str) -> str:
    base = f"{_normalize_email(email)}|{code}|{settings.jwt_secret_key}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _send_verification_email(email: str, code: str, purpose: VerificationPurpose) -> None:
    action = "confirmar sua conta" if purpose == VerificationPurpose.signup else "acessar sua conta"

    if not resend.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Set RESEND_API_KEY.",
        )

    from_email = settings.smtp_from_email or "Nexus Leads <onboarding@resend.dev>"

    try:
        resend.Emails.send({
            "from": from_email,
            "to": [email],
            "subject": f"Nexus Leads - Codigo de verificacao",
            "html": (
                f"<div style='font-family:Inter,Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;'>"
                f"<h2 style='color:#fff;margin:0 0 8px'>Nexus Leads</h2>"
                f"<p style='color:#a1a1aa;margin:0 0 24px'>Codigo para {action}:</p>"
                f"<div style='background:#18181b;border:1px solid rgba(255,255,255,0.08);border-radius:12px;"
                f"padding:24px;text-align:center;margin:0 0 24px'>"
                f"<span style='font-size:32px;font-weight:700;color:#3b82f6;letter-spacing:8px'>{code}</span>"
                f"</div>"
                f"<p style='color:#71717a;font-size:13px'>Expira em {settings.email_code_ttl_minutes} minutos.</p>"
                f"</div>"
            ),
        })
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao enviar email de verificacao.",
        ) from exc


def _create_verification_code(db: Session, user: User, purpose: VerificationPurpose) -> str:
    now = _now()
    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.user_id == user.id,
        EmailVerificationCode.purpose == purpose,
        EmailVerificationCode.consumed_at.is_(None),
    ).update({EmailVerificationCode.consumed_at: now}, synchronize_session=False)

    code = _generate_code()
    row = EmailVerificationCode(
        user_id=user.id,
        purpose=purpose,
        code_hash=_hash_code(user.email, code),
        expires_at=now + timedelta(minutes=settings.email_code_ttl_minutes),
        attempts=0,
    )
    db.add(row)
    db.commit()
    return code


def serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "plan_type": user.plan_type.value,
        "is_admin": user.is_admin,
        "email_verified": user.email_verified,
        "credits_balance": user.credits_balance,
        "billing": usage_payload(user),
        "stripe_customer_id": user.stripe_customer_id,
        "stripe_subscription_id": user.stripe_subscription_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def register_user(db: Session, email: str, password: str, full_name: str | None = None) -> dict:
    normalized_email = _normalize_email(email)

    user = db.query(User).filter(User.email == normalized_email).first()
    if user and user.email_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if not user:
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=(full_name or "").strip() or None,
            plan_type=PlanType.basic,
            email_verified=False,
            is_active=False,
            is_admin=False,
            credits_balance=0,
        )
        apply_plan_policy(user, PlanType.basic)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.password_hash = hash_password(password)
        user.full_name = (full_name or user.full_name or "").strip() or None
        user.email_verified = False
        user.is_active = False
        db.add(user)
        db.commit()
        db.refresh(user)

    code = _create_verification_code(db, user, VerificationPurpose.signup)
    _send_verification_email(user.email, code, VerificationPurpose.signup)

    payload = {
        "ok": True,
        "requires_verification": True,
        "email": user.email,
        "message": "Código de verificação enviado para o email.",
    }
    return payload


def verify_signup_code(db: Session, email: str, code: str) -> User:
    normalized_email = _normalize_email(email)
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    row = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.purpose == VerificationPurpose.signup,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code not found")

    now = _now()
    if row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    if row.code_hash != _hash_code(user.email, code.strip()):
        row.attempts += 1
        db.add(row)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    row.consumed_at = now
    user.email_verified = True
    user.is_active = True
    db.add(row)
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def resend_signup_code(db: Session, email: str) -> dict:
    normalized_email = _normalize_email(email)
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    code = _create_verification_code(db, user, VerificationPurpose.signup)
    _send_verification_email(user.email, code, VerificationPurpose.signup)

    payload = {
        "ok": True,
        "message": "Novo código enviado.",
        "email": user.email,
    }
    return payload


def authenticate_user(db: Session, email: str, password: str) -> User:
    normalized_email = _normalize_email(email)
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()


def bootstrap_admin_user(db: Session) -> None:
    if not settings.auto_bootstrap_admin:
        return

    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    admin = db.query(User).filter(User.email == email).first()

    if not admin:
        admin = User(
            email=email,
            full_name="Admin",
            password_hash=hash_password(password),
            plan_type=PlanType.enterprise,
            email_verified=True,
            is_active=True,
            is_admin=True,
            credits_balance=10_000_000,
        )
        apply_plan_policy(admin, PlanType.enterprise)
        db.add(admin)
        db.commit()
        print(f"[BOOTSTRAP] Admin account created: {email}")
        return

    admin.is_admin = True
    admin.email_verified = True
    admin.is_active = True
    admin.plan_type = PlanType.enterprise
    admin.credits_balance = max(admin.credits_balance, 10_000_000)
    apply_plan_policy(admin, PlanType.enterprise)

    if not verify_password(password, admin.password_hash):
        admin.password_hash = hash_password(password)

    db.add(admin)
    db.commit()


def issue_token_payload(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }

