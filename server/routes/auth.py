from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from server.middleware.auth import verify_token
from server.middleware.rate_limit import check_rate_limit
from server.models import LoginRequest, ChangePasswordRequest
from server.services.auth_service import verify_credentials, create_token, change_password
from server.config import TOKEN_EXPIRE_HOURS

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    check_rate_limit(request)

    if not verify_credentials(req.username, req.password):
        raise HTTPException(401, "Credenciais invalidas")

    token = create_token(req.username)
    resp = JSONResponse({"ok": True, "token": token})
    resp.set_cookie(
        "token", token,
        httponly=True, samesite="lax",
        max_age=TOKEN_EXPIRE_HOURS * 3600,
    )
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("token")
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
