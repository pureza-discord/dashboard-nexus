import uuid

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import decode_access_token
from server.db.models import User
from server.modules.billing.service import reset_usage_if_needed

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _canonical_user_id(raw: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(raw).strip()


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Cookie(default=None, alias="token"),
    db: Session = Depends(get_db),
) -> User:
    raw_token = token or cookie_token
    if not raw_token:
        raise _unauthorized()

    try:
        payload = decode_access_token(raw_token)
        user_id = payload.get("sub")
        if not user_id:
            raise _unauthorized("Invalid token payload")
        parsed_id = _canonical_user_id(str(user_id))
    except Exception as exc:
        raise _unauthorized("Session expired") from exc

    user = db.query(User).filter(User.id == parsed_id, User.is_active.is_(True)).first()
    if not user:
        raise _unauthorized("User not found")

    reset_usage_if_needed(db, user)
    db.commit()

    return user
