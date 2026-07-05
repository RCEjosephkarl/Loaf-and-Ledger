"""F4 — budget tracker: per-category monthly limits + utilization status."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import TxDirection
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas import BudgetCreate, BudgetOut, BudgetStatus
from app.services.currency import convert
from app.tax.models import money

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1) if month < 12 else date(year + 1, 1, 1)
    return start, end


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


@router.delete("/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    budget = db.get(Budget, budget_id)
    if budget is None or budget.user_id != user.id:
        raise HTTPException(404, "Budget not found")
    db.delete(budget)
    db.commit()


@router.get("/status", response_model=list[BudgetStatus])
def budget_status(
    year: int, month: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Spent vs limit per budgeted category for a given month."""
    start, end = _month_bounds(year, month)
    budgets = (
        db.execute(
            select(Budget).where(
                Budget.user_id == user.id, Budget.year == year, Budget.month == month
            )
        )
        .scalars()
        .all()
    )

    out: list[BudgetStatus] = []
    for b in budgets:
        category = db.get(Category, b.category_id)
        txns = (
            db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.category_id == b.category_id,
                    Transaction.direction == TxDirection.OUTBOUND,
                    Transaction.occurred_on >= start,
                    Transaction.occurred_on < end,
                )
            )
            .scalars()
            .all()
        )
        spent = sum(
            (convert(db, Decimal(str(t.amount)), t.currency, b.currency) for t in txns),
            Decimal("0"),
        )
        spent = money(spent)
        limit = Decimal(str(b.limit_amount))
        remaining = money(limit - spent)
        utilization = (spent / limit).quantize(Decimal("0.0001")) if limit > 0 else Decimal("0")
        out.append(
            BudgetStatus(
                category_id=b.category_id,
                category_name=category.name if category else "Unknown",
                year=year,
                month=month,
                limit_amount=money(limit),
                spent=spent,
                remaining=remaining,
                utilization=utilization,
                currency=b.currency,
                over_budget=spent > limit,
            )
        )
    return out
