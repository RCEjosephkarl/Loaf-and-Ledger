"""F4 — budget tracker: per-category limits + utilization status over a
selectable period (month / trailing 3 months / year-to-date / all time), plus
a carry-over "initial fund" per period."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import BudgetScope, Region, TxDirection
from app.models.budget import FUND_ALL_SENTINEL, Budget, FundOverride
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas import BudgetCreate, BudgetOut, BudgetStatus, FundOverrideIn, FundStatus
from app.services import budgets as budgets_svc
from app.services.currency import convert
from app.tax.models import money

router = APIRouter(prefix="/budgets", tags=["budgets"])


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
    category = db.get(Category, payload.category_id)
    if category is None or category.direction != TxDirection.OUTBOUND:
        raise HTTPException(422, "Budgets apply to outbound (expense) categories only")

    existing = db.execute(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.category_id == payload.category_id,
            Budget.year == payload.year,
            Budget.month == payload.month,
        )
    ).scalar_one_or_none()
    currency = (payload.currency or user.base_currency).upper()
    if existing is not None:
        existing.limit_amount = payload.limit_amount
        existing.currency = currency
        db.commit()
        db.refresh(existing)
        return existing

    budget = Budget(
        user_id=user.id,
        category_id=payload.category_id,
        year=payload.year,
        month=payload.month,
        limit_amount=payload.limit_amount,
        currency=currency,
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
    """Spent vs limit per budgeted category, over `scope`'s period at `anchor`
    (or the legacy single `year`+`month`, which is equivalent to
    `scope=month`)."""
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

    by_category: dict[int, list[Budget]] = defaultdict(list)
    for b in rows:
        by_category[b.category_id].append(b)

    out: list[BudgetStatus] = []
    for category_id, blist in by_category.items():
        # Convert every month's limit into the *latest* month's currency —
        # nothing in the app currently handles a user changing currencies
        # mid-year, so this is the simplest coherent policy available.
        latest = max(blist, key=lambda r: (r.year, r.month))
        target_ccy = latest.currency
        limit = money(
            sum(
                (convert(db, Decimal(str(b.limit_amount)), b.currency, target_ccy) for b in blist),
                Decimal("0"),
            )
        )
        txns = (
            db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.category_id == category_id,
                    Transaction.direction == TxDirection.OUTBOUND,
                    Transaction.occurred_on >= start,
                    Transaction.occurred_on < end,
                )
            )
            .scalars()
            .all()
        )
        spent = money(
            sum(
                (convert(db, Decimal(str(t.amount)), t.currency, target_ccy) for t in txns),
                Decimal("0"),
            )
        )
        category = db.get(Category, category_id)
        utilization = (spent / limit).quantize(Decimal("0.0001")) if limit > 0 else Decimal("0")
        out.append(
            BudgetStatus(
                category_id=category_id,
                category_name=category.name if category else "Unknown",
                year=resolved_anchor.year if scope is BudgetScope.MONTH else None,
                month=resolved_anchor.month if scope is BudgetScope.MONTH else None,
                scope=scope.value,
                period_start=start,
                period_end=end - timedelta(days=1),
                limit_amount=limit,
                spent=spent,
                remaining=money(limit - spent),
                utilization=utilization,
                currency=target_ccy,
                over_budget=spent > limit,
            )
        )
    return out


@router.get("/fund", response_model=FundStatus)
def get_fund(
    scope: BudgetScope,
    anchor: date | None = None,
    currency: str | None = None,
    region: Region | None = None,
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

    if override is not None:
        return FundStatus(
            scope=scope,
            period_start=period_start,
            period_end=period_end_excl - timedelta(days=1),
            amount=override.amount,
            currency=override.currency,
            is_override=True,
        )

    ccy = (currency or user.base_currency).upper()
    amount = budgets_svc.default_initial_fund(
        db, user.id, scope=scope, anchor=resolved_anchor, currency=ccy, region=region
    )
    return FundStatus(
        scope=scope,
        period_start=period_start,
        period_end=period_end_excl - timedelta(days=1),
        amount=amount,
        currency=ccy,
        is_override=False,
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
    currency = (payload.currency or user.base_currency).upper()

    existing = db.execute(
        select(FundOverride).where(
            FundOverride.user_id == user.id,
            FundOverride.scope == payload.scope,
            FundOverride.period_start == period_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.amount = payload.amount
        existing.currency = currency
    else:
        existing = FundOverride(
            user_id=user.id,
            scope=payload.scope,
            period_start=period_start,
            amount=payload.amount,
            currency=currency,
        )
        db.add(existing)
    db.commit()

    return FundStatus(
        scope=payload.scope,
        period_start=period_start,
        period_end=period_end_excl - timedelta(days=1),
        amount=existing.amount,
        currency=existing.currency,
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
