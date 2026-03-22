from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from sqlalchemy import text
from server.config import (
    ALGORITHM,
    AUTO_BOOTSTRAP_ADMIN,
    BOOTSTRAP_ADMIN_PASSWORD,
    BOOTSTRAP_ADMIN_USERNAME,
    SECRET_KEY,
    TOKEN_EXPIRE_HOURS,
)
from server.services.db import get_conn

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def init_users_table() -> None:
    with get_conn() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """)
        )
        row = conn.execute(text("SELECT id FROM dashboard_users LIMIT 1")).fetchone()

        if not row and AUTO_BOOTSTRAP_ADMIN:
            bootstrap_password = BOOTSTRAP_ADMIN_PASSWORD or "admin123"
            password_hash = pwd_ctx.hash(bootstrap_password)
            conn.execute(
                text("INSERT INTO dashboard_users (username, password_hash) VALUES (:usr, :pwd)"),
                {"usr": BOOTSTRAP_ADMIN_USERNAME, "pwd": password_hash},
            )
            print("\n[AUTH] Bootstrap admin created.")
            print(f"[AUTH] Username: {BOOTSTRAP_ADMIN_USERNAME}")
            print(f"[AUTH] Password: {bootstrap_password}\n")

        conn.commit()


def verify_credentials(username: str, password: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM dashboard_users WHERE username = :usr"),
            {"usr": username},
        ).fetchone()

    if not row:
        return False
    return pwd_ctx.verify(password, row[0])


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def change_password(username: str, current: str, new_password: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM dashboard_users WHERE username = :usr"),
            {"usr": username},
        ).fetchone()

        if not row or not pwd_ctx.verify(current, row[0]):
            return False

        password_hash = pwd_ctx.hash(new_password)
        conn.execute(
            text("UPDATE dashboard_users SET password_hash = :pwd WHERE username = :usr"),
            {"pwd": password_hash, "usr": username},
        )
        conn.commit()
    return True
