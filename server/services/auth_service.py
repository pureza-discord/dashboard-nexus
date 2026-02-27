import sqlite3
from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from server.config import DB_PATH, SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_HOURS

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def init_users_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin'
            )
            """
        )
        row = conn.execute("SELECT id FROM dashboard_users LIMIT 1").fetchone()
        if not row:
            h = pwd_ctx.hash("admin123")
            conn.execute(
                "INSERT INTO dashboard_users (username, password_hash) VALUES (?, ?)",
                ("admin", h),
            )
        conn.commit()


def verify_credentials(username: str, password: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash FROM dashboard_users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return False
    return pwd_ctx.verify(password, row[0])


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def change_password(username: str, current: str, new_password: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash FROM dashboard_users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row or not pwd_ctx.verify(current, row[0]):
            return False
        h = pwd_ctx.hash(new_password)
        conn.execute(
            "UPDATE dashboard_users SET password_hash = ? WHERE username = ?",
            (h, username),
        )
        conn.commit()
    return True
