"""F6 — dashboard summary honoring the global time-range filter."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import CURRENCY, AccountType
from app.models.user import User
from app.routers.analytics import salary_reference
from app.schemas import AccountTotal, DashboardSummary, Insight
from app.services import balances as balances_svc
from app.services import insights as insights_svc
from app.tax.models import money
from app.warehouse import queries as wq

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    totals = wq.totals(start, end, account_id)
    accounts = wq.by_account(start, end, account_id)
    net_period, _ = salary_reference(db, user.id)

    expenses = [a for a in accounts if a["flow_class"] == "outflow"]
    top = sorted(expenses, key=lambda a: a["total"], reverse=True)[:5]

    # Net worth comes from the OLTP balances rather than the warehouse: it is a
    # point-in-time stock, not a windowed flow, and the journal is its source.
    rows = balances_svc.account_balances(db, user.id)
    assets = sum(
        (r.balance for r in rows if r.type is AccountType.ASSET), start=money("0")
    )
    liabilities = sum(
        (r.balance for r in rows if r.type is AccountType.LIABILITY), start=money("0")
    )

    return DashboardSummary(
        currency=CURRENCY,
        total_income=totals["total_income"],
        total_expense=totals["total_expense"],
        net_cashflow=totals["net_cashflow"],
        transfer_volume=totals["transfer_volume"],
        salary_net_period=net_period,
        savings_rate=insights_svc.savings_rate(
            totals["total_income"], totals["total_expense"]
        ),
        net_worth=money(assets - liabilities),
        top_expense_accounts=[AccountTotal(**a) for a in top],
        insights=[
            Insight(**i)
            for i in insights_svc.generate(
                totals=totals,
                accounts=accounts,
                salary_net_period=net_period,
                transfer_volume=totals["transfer_volume"],
            )
        ],
    )
