"""F3 — analytics, served from the OLAP warehouse.

Every endpoint here is a thin translation of a warehouse query into a response
model. The aggregation itself happens in DuckDB (see app/warehouse/queries.py),
not in Python — which is the whole point of having a second store.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import CURRENCY
from app.models.salary import SalaryProfile
from app.models.user import User
from app.schemas import (
    AccountTotal,
    AnalyticsOverview,
    EarningsResponse,
    MonthlyByAccountResponse,
    MonthlyResponse,
    RunningBalanceResponse,
)
from app.services import insights as insights_svc
from app.warehouse import queries as wq

router = APIRouter(prefix="/analytics", tags=["analytics"])


def active_salary(db: Session, user_id: int) -> SalaryProfile | None:
    return (
        db.execute(
            select(SalaryProfile)
            .where(SalaryProfile.user_id == user_id, SalaryProfile.is_active.is_(True))
            .order_by(SalaryProfile.updated_at.desc())
        )
        .scalars()
        .first()
    )


def salary_reference(db: Session, user_id: int) -> tuple[Decimal | None, Decimal | None]:
    """(net per period, effective deduction rate) from the active payslip."""
    profile = active_salary(db, user_id)
    if profile is None:
        return None, None
    breakdown = profile.breakdown or {}
    net = Decimal(str(breakdown.get("net_period", "0")))
    rate = Decimal(str(breakdown.get("effective_rate", "0")))
    return (net or None), rate


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Income/expense totals plus the per-account breakdown behind them."""
    totals = wq.totals(start, end, account_id)
    accounts = wq.by_account(start, end, account_id)
    net_period, deduction_rate = salary_reference(db, user.id)

    return AnalyticsOverview(
        currency=CURRENCY,
        total_income=totals["total_income"],
        total_expense=totals["total_expense"],
        net_cashflow=totals["net_cashflow"],
        transfer_volume=totals["transfer_volume"],
        salary_net_period=net_period,
        salary_deduction_rate=deduction_rate,
        savings_rate=insights_svc.savings_rate(
            totals["total_income"], totals["total_expense"]
        ),
        accounts=[AccountTotal(**a) for a in accounts],
    )


@router.get("/monthly", response_model=MonthlyResponse)
def monthly(months: int = Query(6, ge=1, le=36)):
    """Monthly income vs expense, straight off the monthly rollup."""
    return MonthlyResponse(currency=CURRENCY, series=wq.monthly(months))


@router.get("/monthly-by-account", response_model=MonthlyByAccountResponse)
def monthly_by_account(
    months: int = Query(6, ge=1, le=36),
    flow: str = Query("outflow", pattern="^(inflow|outflow)$"),
):
    """Trailing-N-month totals per account — feeds the stacked mix chart."""
    result = wq.monthly_by_account(months, flow)
    return MonthlyByAccountResponse(currency=CURRENCY, **result)


@router.get("/running-balance", response_model=RunningBalanceResponse)
def running_balance(start: date | None = None, end: date | None = None):
    """Daily in/out with a cumulative balance across the range."""
    return RunningBalanceResponse(currency=CURRENCY, points=wq.running_balance(start, end))


@router.get("/earnings", response_model=EarningsResponse)
def earnings(profile_id: int | None = None):
    """The gross-to-net story: what was earned, what was withheld, what landed.

    Read from fact_payslip_item rather than parsing the profile's JSON
    snapshot, so the waterfall and the ledger agree by construction.
    """
    result = wq.earnings_breakdown(profile_id)
    return EarningsResponse(currency=CURRENCY, **result)
