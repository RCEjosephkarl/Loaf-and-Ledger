"""F4 — budget tracker: per-account limits + utilization over a selectable
period (month / trailing 3 months / year-to-date / all time), plus a
carry-over "initial fund" per period.

Spend comes from the warehouse: it is an aggregation over a date window, which
is exactly what the OLAP side exists to answer.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.account import Account
from app.models.base import AccountType, BudgetScope
from app.models.budget import FUND_ALL_SENTINEL, Budget, FundOverride
from app.models.user import User
from app.schemas import BudgetCreate, BudgetOut, BudgetStatus, FundOverrideIn, FundStatus
from app.services import budgets as budgets_svc
from app.tax.models import money
from app.warehouse import queries as wq

router = APIRouter(prefix="/budgets", tags=["budgets"])

ZERO = Decimal("0")


def _fund_period_start(db: Session, user_id: int, scope: BudgetScope, anchor: date) -> date:
    if scope is BudgetScope.ALL:
        return FUND_ALL_SENTINEL
    start, _, _ = budgets_svc.period_bounds(db, user_id, scope, anchor)
    return start


@router.get("", response_model=list[BudgetOut])
def list_budgets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return (
        db.execute(
            select(Budget).where(Budget.user_id == user.id).order_by(Budget.year, Budget.month)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=BudgetOut, status_code=201)
def upsert_budget(
    payload: BudgetCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    account = db.get(Account, payload.account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")
    if account.type is not AccountType.EXPENSE:
        raise HTTPException(422, "Budgets apply to expense accounts only")

    existing = db.execute(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.account_id == payload.account_id,
            Budget.year == payload.year,
            Budget.month == payload.month,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.limit_amount = payload.limit_amount
        db.commit()
        db.refresh(existing)
        return existing

    budget = Budget(
        user_id=user.id,
        account_id=payload.account_id,
        year=payload.year,
        month=payload.month,
        limit_amount=payload.limit_amount,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/status", response_model=list[BudgetStatus])
def budget_status(
    year: int | None = None,
    month: int | None = None,
    scope: BudgetScope | None = None,
    anchor: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Spent vs limit per budgeted account, over `scope`'s period at `anchor`
    (or the legacy single `year`+`month`, equivalent to `scope=month`)."""
    if scope is None:
        if year is None or month is None:
            raise HTTPException(422, "Provide scope(+anchor) or year+month")
        scope, resolved_anchor = BudgetScope.MONTH, date(year, month, 1)
    else:
        resolved_anchor = anchor or date.today()

    start, end, months = budgets_svc.period_bounds(db, user.id, scope, resolved_anchor)
    if not months:
        return []
    months_set = set(months)

    # Single-user, small table — fetch-all + filter-in-Python is simpler and
    # more portable across SQLite/Postgres than a tuple_(year, month).in_(...).
    all_budgets = db.execute(select(Budget).where(Budget.user_id == user.id)).scalars().all()
    rows = [b for b in all_budgets if (b.year, b.month) in months_set]

    limits: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for b in rows:
        limits[b.account_id] += Decimal(str(b.limit_amount))

    # One warehouse query covers every account in the window, replacing the old
    # per-category SELECT loop.
    spend = wq.spend_by_account(start, end)
    accounts = {
        a.id: a
        for a in db.execute(select(Account).where(Account.id.in_(limits.keys()))).scalars().all()
    }

    out: list[BudgetStatus] = []
    for account_id, limit_total in limits.items():
        limit = money(limit_total)
        spent = money(spend.get(account_id, ZERO))
        account = accounts.get(account_id)
        utilization = (spent / limit).quantize(Decimal("0.0001")) if limit > 0 else ZERO
        out.append(
            BudgetStatus(
                account_id=account_id,
                account_name=account.name if account else "Unknown",
                account_code=account.code if account else "—",
                year=resolved_anchor.year if scope is BudgetScope.MONTH else None,
                month=resolved_anchor.month if scope is BudgetScope.MONTH else None,
                scope=scope.value,
                period_start=start,
                period_end=end - timedelta(days=1),
                limit_amount=limit,
                spent=spent,
                remaining=money(limit - spent),
                utilization=utilization,
                over_budget=spent > limit,
            )
        )
    return sorted(out, key=lambda s: s.utilization, reverse=True)


@router.get("/fund", response_model=FundStatus)
def get_fund(
    scope: BudgetScope,
    anchor: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """The period's "initial fund" — an override if the user set one, else
    the computed carry-over default (prior period's ending balance)."""
    resolved_anchor = anchor or date.today()
    _, period_end_excl, _ = budgets_svc.period_bounds(db, user.id, scope, resolved_anchor)
    period_start = _fund_period_start(db, user.id, scope, resolved_anchor)

    override = db.execute(
        select(FundOverride).where(
            FundOverride.user_id == user.id,
            FundOverride.scope == scope,
            FundOverride.period_start == period_start,
        )
    ).scalar_one_or_none()

    amount = (
        override.amount
        if override is not None
        else budgets_svc.default_initial_fund(scope, resolved_anchor)
    )
    return FundStatus(
        scope=scope,
        period_start=period_start,
        period_end=period_end_excl - timedelta(days=1),
        amount=amount,
        is_override=override is not None,
    )


@router.post("/fund", response_model=FundStatus)
def set_fund(
    payload: FundOverrideIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Upsert an override for the period's initial fund (matches this
    router's existing POST-as-upsert convention, see `upsert_budget`)."""
    resolved_anchor = payload.anchor or date.today()
    period_start = _fund_period_start(db, user.id, payload.scope, resolved_anchor)
    _, period_end_excl, _ = budgets_svc.period_bounds(db, user.id, payload.scope, resolved_anchor)

    existing = db.execute(
        select(FundOverride).where(
            FundOverride.user_id == user.id,
            FundOverride.scope == payload.scope,
            FundOverride.period_start == period_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.amount = payload.amount
    else:
        existing = FundOverride(
            user_id=user.id,
            scope=payload.scope,
            period_start=period_start,
            amount=payload.amount,
        )
        db.add(existing)
    db.commit()

    return FundStatus(
        scope=payload.scope,
        period_start=period_start,
        period_end=period_end_excl - timedelta(days=1),
        amount=existing.amount,
        is_override=True,
    )


@router.delete("/fund", status_code=204)
def reset_fund(
    scope: BudgetScope,
    anchor: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Remove an override, reverting the period to its computed default."""
    resolved_anchor = anchor or date.today()
    period_start = _fund_period_start(db, user.id, scope, resolved_anchor)
    existing = db.execute(
        select(FundOverride).where(
            FundOverride.user_id == user.id,
            FundOverride.scope == scope,
            FundOverride.period_start == period_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.commit()


# Registered last: "/{budget_id}" is a catch-all path parameter that would
# otherwise shadow the literal "/status" and "/fund" routes above (FastAPI
# matches routes in registration order).
@router.delete("/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    budget = db.get(Budget, budget_id)
    if budget is None or budget.user_id != user.id:
        raise HTTPException(404, "Budget not found")
    db.delete(budget)
    db.commit()
