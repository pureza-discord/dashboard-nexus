from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from server.core.security import create_access_token, hash_password, verify_password
from server.core.settings import get_settings
from server.db.models import PlanType, User, VerificationPurpose, VerificationToken
from server.modules.billing.service import apply_plan_policy, usage_payload
from server.services.email_service import get_last_dev_code, send_verification_email

settings = get_settings()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _now() -> datetime:
    return datetime.utcnow()


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _hash_code(email: str, code: str) -> str:
    base = f"{_normalize_email(email)}|{code}|{settings.jwt_secret_key}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _parse_purpose(raw: str | VerificationPurpose) -> VerificationPurpose:
    if isinstance(raw, VerificationPurpose):
        return raw
    value = (raw or "signup").strip().lower()
    if value in {"signup", "register", "verify_email"}:
        return VerificationPurpose.signup
    if value in {"login", "signin"}:
        return VerificationPurpose.login
    if value in {"password_reset", "reset", "forgot_password"}:
        return VerificationPurpose.password_reset
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification purpose")


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == _normalize_email(email)).first()


def _issue_verification_token(db: Session, user: User, purpose: VerificationPurpose) -> str:
    now = _now()
    (
        db.query(VerificationToken)
        .filter(
            VerificationToken.user_id == user.id,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
        )
        .update({VerificationToken.consumed_at: now}, synchronize_session=False)
    )

    code = _generate_code()
    row = VerificationToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=_hash_code(user.email, code),
        expires_at=now + timedelta(minutes=settings.email_code_ttl_minutes),
        attempts=0,
    )
    db.add(row)
    db.commit()
    return code


def _assert_valid_token(db: Session, user: User, code: str, purpose: VerificationPurpose) -> VerificationToken:
    row = (
        db.query(VerificationToken)
        .filter(
            VerificationToken.user_id == user.id,
            VerificationToken.purpose == purpose,
            VerificationToken.consumed_at.is_(None),
        )
        .order_by(VerificationToken.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code not found")

    now = _now()
    if row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    if row.token_hash != _hash_code(user.email, code.strip()):
        row.attempts += 1
        db.add(row)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    row.consumed_at = now
    db.add(row)
    db.commit()
    return row


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


def send_verification_code(db: Session, email: str, purpose: str | VerificationPurpose = VerificationPurpose.signup) -> dict:
    parsed_purpose = _parse_purpose(purpose)
    normalized_email = _normalize_email(email)

    user = _get_user_by_email(db, normalized_email)
    if not user:
        if parsed_purpose != VerificationPurpose.signup:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user = User(
            email=normalized_email,
            password_hash=hash_password(_generate_code() + settings.jwt_secret_key[:8]),
            full_name=None,
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

    code = _issue_verification_token(db, user, parsed_purpose)
    send_verification_email(user.email, code, parsed_purpose)

    result: dict = {
        "ok": True,
        "email": user.email,
        "purpose": parsed_purpose.value,
        "message": "Codigo enviado com sucesso.",
    }

    if settings.environment != "production":
        dev_code = get_last_dev_code(user.email)
        if dev_code:
            result["dev_code"] = dev_code

    return result


def verify_code(db: Session, email: str, code: str, purpose: str | VerificationPurpose = VerificationPurpose.signup) -> User:
    parsed_purpose = _parse_purpose(purpose)
    user = _get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _assert_valid_token(db, user, code, parsed_purpose)

    if parsed_purpose in {VerificationPurpose.signup, VerificationPurpose.login}:
        user.email_verified = True
        user.is_active = True

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, email: str, password: str, full_name: str | None = None) -> dict:
    normalized_email = _normalize_email(email)
    user = _get_user_by_email(db, normalized_email)

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

    send_verification_code(db, normalized_email, VerificationPurpose.signup)

    result: dict = {
        "ok": True,
        "requires_verification": True,
        "email": user.email,
        "message": "Codigo de verificacao enviado para o email.",
    }

    if settings.environment != "production":
        dev_code = get_last_dev_code(user.email)
        if dev_code:
            result["dev_code"] = dev_code

    return result


def verify_signup_code(db: Session, email: str, code: str) -> User:
    return verify_code(db, email, code, VerificationPurpose.signup)


def resend_signup_code(db: Session, email: str) -> dict:
    return send_verification_code(db, email, VerificationPurpose.signup)


def forgot_password(db: Session, email: str) -> dict:
    user = _get_user_by_email(db, email)
    if not user:
        return {"ok": True, "message": "Se o email existir, um codigo sera enviado."}

    send_verification_code(db, email, VerificationPurpose.password_reset)
    result: dict = {"ok": True, "message": "Codigo de redefinicao enviado para o email."}

    if settings.environment != "production":
        dev_code = get_last_dev_code(email)
        if dev_code:
            result["dev_code"] = dev_code

    return result


def reset_password(db: Session, email: str, code: str, new_password: str) -> User:
    user = verify_code(db, email, code, VerificationPurpose.password_reset)
    user.password_hash = hash_password(new_password)
    user.email_verified = True
    user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
