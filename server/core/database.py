from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from server.core.settings import PROJECT_ROOT, get_settings

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


def _needs_migration() -> bool:
    """Check if alembic migration is needed (fast, no lock contention)."""
    try:
        with engine.connect() as conn:
            tables = inspect(conn).get_table_names()
            if "alembic_version" not in tables:
                return True
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            return row is None
    except Exception:
        return True


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_ini = Path(PROJECT_ROOT) / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # For SQLite, dispose pooled connections to avoid file locking during migration
    if settings.database_url.startswith("sqlite"):
        engine.dispose()

    command.upgrade(cfg, "head")


def init_db() -> None:
    if _needs_migration():
        run_migrations()


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
