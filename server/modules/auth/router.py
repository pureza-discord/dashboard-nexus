from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from server.api.deps import get_current_user
from server.core.database import get_db
from server.core.settings import get_settings
from server.db.models import User
from server.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendCodeRequest,
    VerifyEmailCodeRequest,
)
from server.modules.auth.service import (
    authenticate_user,
    change_password,
    issue_token_payload,
    register_user,
    resend_signup_code,
    serialize_user,
    verify_signup_code,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _set_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, payload.email, payload.password, payload.full_name)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailCodeRequest, response: Response, db: Session = Depends(get_db)):
    user = verify_signup_code(db, payload.email, payload.code)
    token_payload = issue_token_payload(user)
    _set_token_cookie(response, token_payload["access_token"])
    return token_payload


@router.post("/resend-verification")
def resend_verification(payload: ResendCodeRequest, db: Session = Depends(get_db)):
    return resend_signup_code(db, payload.email)


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    token_payload = issue_token_payload(user)
    _set_token_cookie(response, token_payload["access_token"])
    return token_payload


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("token")
    return {"ok": True}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.post("/change-password")
def update_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    change_password(db, current_user, payload.current_password, payload.new_password)
    return {"ok": True}
