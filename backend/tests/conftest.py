"""Pytest fixtures: isolated OLTP (SQLite) + OLAP (DuckDB) stores per test.

Both stores are built in `tmp_path`, so a test run never touches the developer's
loaf_ledger.db or warehouse.duckdb, and each test starts from an empty pair.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import enable_sqlite_foreign_keys, get_db
from app.main import app
from app.models import Account, AccountType, Base
from app.seed import seed_chart, seed_demo
from app.services.user import get_single_user
from app.warehouse import engine as warehouse_engine
from app.warehouse import etl


@pytest.fixture
def warehouse(tmp_path):
    """Point the warehouse module at a throwaway DuckDB file."""
    path = str(tmp_path / "test_warehouse.duckdb")
    warehouse_engine.reset(path)
    # The module reads its path from settings on every connect, so override it
    # for the duration of the test rather than relying on the cached handle.
    from app.config import get_settings

    settings = get_settings()
    original = settings.warehouse_path
    settings.warehouse_path = path
    yield path
    settings.warehouse_path = original
    warehouse_engine.reset(None)


@pytest.fixture
def db_session(tmp_path, warehouse):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def chart(db_session):
    """The seeded PH chart of accounts, keyed by code."""
    user = get_single_user(db_session)
    return seed_chart(db_session, user.id)


@pytest.fixture
def user_id(db_session) -> int:
    return get_single_user(db_session).id


@pytest.fixture
def seeded_db(db_session):
    """Full demo dataset, with the warehouse loaded from it."""
    seed_demo(db_session)
    etl.rebuild_all(db_session)
    return db_session


@pytest.fixture
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_client(seeded_db):
    def _override():
        yield seeded_db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def accounts(client, chart):
    """Chart fixture usable from API tests, keyed by code."""
    return chart


def make_account(db, user_id: int, code: str, name: str, type_: AccountType) -> Account:
    account = Account(user_id=user_id, code=code, name=name, type=type_, is_system=False)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def at(day: int, month: int = 6, year: int = 2026, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0)
