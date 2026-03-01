from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from server.core.database import SessionLocal


@contextmanager
def get_conn(*, row_factory: bool = False) -> Iterator[Session]:
    # Backward-compatible wrapper kept for legacy imports.
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
