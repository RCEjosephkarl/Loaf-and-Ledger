"""Exercise the actual SQLite upgrade and guarded downgrade on a disposable database."""

from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.salary import PayPeriod, SalaryProfile
from app.models.user import User


def test_salary_enum_migration_preserves_snapshots_and_guards_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/migration.db"
    monkeypatch.setattr(get_settings(), "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_initial_double_entry")
    db_engine = create_engine(url)
    snapshot = {"gross_period": "1000.00", "net_period": "900.00", "items": []}
    with Session(db_engine) as db:
        user = User(name="Migration test")
        db.add(user)
        db.flush()
        profile = SalaryProfile(
            user_id=user.id,
            label="Existing salary",
            gross_amount=Decimal("1000"),
            pay_period=PayPeriod.MONTHLY,
            tax_year=2025,
            breakdown=snapshot,
        )
        db.add(profile)
        db.commit()
        profile_id = profile.id

    command.upgrade(config, "head")
    columns = {
        column["name"]: column for column in inspect(db_engine).get_columns("salary_profiles")
    }
    assert columns["pay_period"]["type"].length == 11
    with Session(db_engine) as db:
        profile = db.get(SalaryProfile, profile_id)
        assert profile.breakdown == snapshot
        profile.pay_period = PayPeriod.FORTNIGHTLY
        db.commit()
    with pytest.raises(RuntimeError, match="Remove fortnightly profiles"):
        command.downgrade(config, "0001_initial_double_entry")
    with Session(db_engine) as db:
        profile = db.get(SalaryProfile, profile_id)
        assert profile.pay_period == PayPeriod.FORTNIGHTLY
        profile.pay_period = PayPeriod.MONTHLY
        db.commit()
    command.downgrade(config, "0001_initial_double_entry")
    command.upgrade(config, "head")
    with Session(db_engine) as db:
        assert db.get(SalaryProfile, profile_id).breakdown == snapshot
    db_engine.dispose()
