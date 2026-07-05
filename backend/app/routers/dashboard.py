"""F6 — dashboard summary honoring global filters (time range, currency, region)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import Region
from app.models.user import User
from app.schemas import CategoryTotal, DashboardSummary, Insight
from app.services import analytics as svc
from app.services.currency import convert

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    currency: str | None = None,
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ccy = (currency or user.base_currency).upper()
    agg = svc.aggregate(db, user.id, currency=ccy, start=start, end=end, region=region)

    salary = svc.active_salary(db, user.id)
    salary_net_period = None
    if salary is not None:
        net_period = Decimal(str(salary.breakdown.get("net_period", "0")))
        salary_net_period = convert(db, net_period, salary.currency, ccy)

    reference = salary_net_period if salary_net_period else agg["total_income"]
    insights = svc.generate_insights(
        db, user.id, currency=ccy, agg=agg, salary_net_period=salary_net_period
    )

    return DashboardSummary(
        currency=ccy,
        region=region,
        total_income=agg["total_income"],
        total_expense=agg["total_expense"],
        net_cashflow=agg["net_cashflow"],
        salary_net_period=salary_net_period,
        savings_rate=svc.savings_rate(reference, agg["total_expense"]),
        top_expense_categories=[CategoryTotal(**c) for c in svc.top_expense_categories(agg)],
        insights=[Insight(**i) for i in insights],
    )
