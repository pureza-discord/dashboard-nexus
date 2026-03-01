from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from server.middleware.auth import verify_token
from server.middleware.rate_limit import check_rate_limit
from server.models import LoginRequest, ChangePasswordRequest
from server.services.auth_service import verify_credentials, create_token, change_password
from server.config import TOKEN_EXPIRE_HOURS, COOKIE_DOMAIN, COOKIE_SAMESITE, COOKIE_SECURE

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    check_rate_limit(request)

    if not verify_credentials(req.username, req.password):
        raise HTTPException(401, "Credenciais invalidas")

    token = create_token(req.username)
    resp = JSONResponse(
        {
            "ok": True,
            "token": token,
            "username": req.username,
            "expires_in_hours": TOKEN_EXPIRE_HOURS,
        }
    )
    resp.set_cookie(
        "token", token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        domain=COOKIE_DOMAIN,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
    )
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token", domain=COOKIE_DOMAIN)
    return resp


@router.get("/me")
async def me(user: str = Depends(verify_token)):
    return {"username": user}


@router.post("/change-password")
async def change_pw(req: ChangePasswordRequest, user: str = Depends(verify_token)):
    ok = change_password(user, req.current, req.new_password)
    if not ok:
        raise HTTPException(400, "Senha atual incorreta")
    return {"ok": True}
