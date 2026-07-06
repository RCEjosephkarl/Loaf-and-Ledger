"""Unit tests for budget period math (services/budgets.py) — no API layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.base import BudgetScope
from app.models.budget import Budget
from app.services.budgets import period_bounds, previous_period_end


def test_month_scope(db_session):
    start, end, months = period_bounds(db_session, 1, BudgetScope.MONTH, date(2026, 6, 15))
    assert (start, end, months) == (date(2026, 6, 1), date(2026, 7, 1), [(2026, 6)])


def test_quarter_scope_year_rollover(db_session):
    """Anchored in January: the trailing 3-month window reaches back into
    the prior year (Nov/Dec of the previous year + Jan of this one)."""
    start, end, months = period_bounds(db_session, 1, BudgetScope.QUARTER, date(2026, 1, 10))
    assert start == date(2025, 11, 1)
    assert end == date(2026, 2, 1)
    assert months == [(2025, 11), (2025, 12), (2026, 1)]


def test_ytd_scope(db_session):
    start, end, months = period_bounds(db_session, 1, BudgetScope.YTD, date(2026, 3, 20))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 4, 1)
    assert months == [(2026, 1), (2026, 2), (2026, 3)]


def test_all_scope_without_budgets_falls_back_to_anchor_month(db_session):
    start, end, months = period_bounds(db_session, 1, BudgetScope.ALL, date(2026, 5, 1))
    assert (start, end, months) == (date(2026, 5, 1), date(2026, 6, 1), [])


def test_all_scope_spans_every_budgeted_month(db_session):
    db_session.add_all(
        [
            Budget(user_id=1, category_id=1, year=2025, month=11, limit_amount=Decimal("100"), currency="USD"),
            Budget(user_id=1, category_id=1, year=2026, month=3, limit_amount=Decimal("100"), currency="USD"),
        ]
    )
    db_session.commit()

    start, end, months = period_bounds(db_session, 1, BudgetScope.ALL, date(2026, 6, 1))
    assert start == date(2025, 11, 1)
    assert end == date(2026, 4, 1)
    assert months == [(2025, 11), (2026, 3)]


def test_previous_period_end_month():
    assert previous_period_end(BudgetScope.MONTH, date(2026, 6, 15)) == date(2026, 5, 31)


def test_previous_period_end_quarter_year_rollover():
    assert previous_period_end(BudgetScope.QUARTER, date(2026, 1, 10)) == date(2025, 10, 31)


def test_previous_period_end_ytd():
    assert previous_period_end(BudgetScope.YTD, date(2026, 3, 20)) == date(2025, 12, 31)


def test_previous_period_end_all_is_none():
    assert previous_period_end(BudgetScope.ALL, date(2026, 3, 20)) is None
