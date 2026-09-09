"""Period math for the budget tracker (F4): translates a `BudgetScope` +
anchor date into calendar-month coverage, and computes the carry-over
default for a period's "initial fund"."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import BudgetScope
from app.models.budget import Budget
from app.warehouse import queries as wq

ZERO = Decimal("0")


def _add_months(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def period_bounds(
    db: Session, user_id: int, scope: BudgetScope, anchor: date
) -> tuple[date, date, list[tuple[int, int]]]:
    """(start, end_exclusive, [(year, month), ...]) covered by `scope` at `anchor`."""
    if scope is BudgetScope.MONTH:
        start = date(anchor.year, anchor.month, 1)
        end = date(*_add_months(anchor.year, anchor.month, 1), 1)
        months = [(anchor.year, anchor.month)]
    elif scope is BudgetScope.QUARTER:
        y0, m0 = _add_months(anchor.year, anchor.month, -2)
        start = date(y0, m0, 1)
        end = date(*_add_months(anchor.year, anchor.month, 1), 1)
        months = [_add_months(y0, m0, i) for i in range(3)]
    elif scope is BudgetScope.YTD:
        start = date(anchor.year, 1, 1)
        end = date(*_add_months(anchor.year, anchor.month, 1), 1)
        months = [(anchor.year, m) for m in range(1, anchor.month + 1)]
    else:  # ALL — every month that has budget data for this user
        rows = db.execute(select(Budget.year, Budget.month).where(Budget.user_id == user_id)).all()
        months = sorted({(y, m) for y, m in rows})
        if months:
            start = date(months[0][0], months[0][1], 1)
            end = date(*_add_months(*months[-1], 1), 1)
        else:
            start = date(anchor.year, anchor.month, 1)
            end = date(*_add_months(anchor.year, anchor.month, 1), 1)
    return start, end, months


def previous_period_end(scope: BudgetScope, anchor: date) -> date | None:
    """Last day of the period immediately before `scope`'s window at `anchor`.
    None for ALL — an open-ended view has no natural predecessor."""
    if scope is BudgetScope.ALL:
        return None
    if scope is BudgetScope.MONTH:
        start = date(anchor.year, anchor.month, 1)
    elif scope is BudgetScope.QUARTER:
        y0, m0 = _add_months(anchor.year, anchor.month, -2)
        start = date(y0, m0, 1)
    else:  # YTD -> Dec 31 of the prior year
        start = date(anchor.year, 1, 1)
    return start - timedelta(days=1)


def default_initial_fund(scope: BudgetScope, anchor: date) -> Decimal:
    """Carry-over default: the all-time cumulative net cash flow as of the day
    before the period starts.

    There is no stored "opening balance" concept for a period, so the only
    coherent definition of "what you had going into this one" is the running
    total the warehouse already maintains, read at the period boundary.
    """
    end = previous_period_end(scope, anchor)
    if end is None:
        return ZERO
    return wq.cumulative_balance_as_of(end)
