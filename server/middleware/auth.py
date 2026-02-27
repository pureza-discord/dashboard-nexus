from fastapi import HTTPException, Request
from jose import JWTError, jwt

from server.config import SECRET_KEY, ALGORITHM


def verify_token(request: Request) -> str:
    token = request.cookies.get("token") or ""
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Nao autenticado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Token invalido")
        return username
    except JWTError:
        raise HTTPException(401, "Sessao expirada")
