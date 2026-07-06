"""F3 — cross-metric analytics derived from salary (F1) + ledger (F2)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import Region, TxDirection
from app.models.user import User
from app.schemas import CategoryTotal, MonthlyByCategoryResponse, RunningBalancePoint
from app.services import analytics as svc
from app.services.currency import convert
from app.tax.models import money

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _resolve_currency(currency: str | None, user: User) -> str:
    return (currency or user.base_currency).upper()


@router.get("/overview")
def overview(
    currency: str | None = None,
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Income/expense totals, per-category breakdown, and salary-vs-spend."""
    ccy = _resolve_currency(currency, user)
    agg = svc.aggregate(db, user.id, currency=ccy, start=start, end=end, region=region)

    salary = svc.active_salary(db, user.id)
    salary_net_period = None
    deduction_rate = None
    if salary is not None:
        net_period = Decimal(str(salary.breakdown.get("net_period", "0")))
        salary_net_period = convert(db, net_period, salary.currency, ccy)
        deduction_rate = Decimal(str(salary.breakdown.get("effective_rate", "0")))

    reference = salary_net_period if salary_net_period else agg["total_income"]
    return {
        "currency": ccy,
        "region": region,
        "total_income": agg["total_income"],
        "total_expense": agg["total_expense"],
        "net_cashflow": agg["net_cashflow"],
        "salary_net_period": salary_net_period,
        "salary_deduction_rate": deduction_rate,
        "savings_rate": svc.savings_rate(reference, agg["total_expense"]),
        "categories": [CategoryTotal(**c) for c in agg["per_category"]],
    }


@router.get("/monthly")
def monthly(
    currency: str | None = None,
    months: int = Query(6, ge=1, le=36),
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Monthly income vs expense time series (converted to `currency`)."""
    ccy = _resolve_currency(currency, user)
    txns = svc._query_transactions(db, user.id, None, None, region)

    buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0")}
    )
    for tx in txns:
        key = f"{tx.occurred_on.year:04d}-{tx.occurred_on.month:02d}"
        amt = convert(db, Decimal(str(tx.amount)), tx.currency, ccy)
        side = "income" if tx.direction == TxDirection.INBOUND else "expense"
        buckets[key][side] += amt

    series = [
        {
            "month": k,
            "income": money(v["income"]),
            "expense": money(v["expense"]),
            "net": money(v["income"] - v["expense"]),
        }
        for k, v in sorted(buckets.items())
    ][-months:]
    return {"currency": ccy, "series": series}


@router.get("/monthly-by-category", response_model=MonthlyByCategoryResponse)
def monthly_by_category(
    currency: str | None = None,
    months: int = Query(6, ge=1, le=36),
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Trailing-N-month expense breakdown per category — feeds the Analytics
    stacked-by-category chart."""
    ccy = _resolve_currency(currency, user)
    result = svc.monthly_expense_by_category(db, user.id, currency=ccy, months=months, region=region)
    return MonthlyByCategoryResponse(currency=ccy, **result)


@router.get("/running-balance")
def running_balance(
    currency: str | None = None,
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Cumulative net cash flow over the range — feeds the Analytics cash-flow
    trend chart and the Budgets running-balance chart (item 2c / item 7)."""
    ccy = _resolve_currency(currency, user)
    points = svc.running_balance(db, user.id, currency=ccy, start=start, end=end, region=region)
    return {
        "currency": ccy,
        "points": [RunningBalancePoint(**p) for p in points],
    }
