"""OLTP database engine, session factory, and FastAPI dependency.

This is the *write* side — the system of record. The analytical side lives in
:mod:`app.warehouse` and is derived from these tables.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite needs check_same_thread disabled for the threaded dev server; Postgres
# ignores connect_args. Same code path, backend chosen purely by DATABASE_URL.
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)


def enable_sqlite_foreign_keys(engine_) -> None:
    """SQLite ignores REFERENCES clauses unless foreign keys are switched on
    per connection — without this the schema's FKs are decorative, and
    ON DELETE CASCADE on journal_lines silently does nothing."""

    @event.listens_for(engine_, "connect")
    def _fk_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


if _is_sqlite:
    enable_sqlite_foreign_keys(engine)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """Yield a request-scoped session, closing it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
