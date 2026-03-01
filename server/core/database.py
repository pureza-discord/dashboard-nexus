from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from server.core.settings import get_settings
from server.db.base import Base

settings = get_settings()

if settings.database_url.startswith("sqlite"):
    db_file = settings.database_url.replace("sqlite:///", "", 1)
    if db_file:
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def init_db() -> None:
    from server.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
