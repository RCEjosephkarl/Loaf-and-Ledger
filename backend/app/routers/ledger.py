"""F2 — ledger: categories + categorized inbound/outbound transactions."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import REGION_CURRENCY, Region, TxDirection
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    TransactionBalancesResponse,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from app.services import analytics as analytics_svc

router = APIRouter(prefix="/ledger", tags=["ledger"])


# ------------------------------------------------------------------ categories


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    direction: TxDirection | None = None,
    include_statutory: bool = True,
    db: Session = Depends(get_db),
):
    stmt = select(Category)
    if direction is not None:
        stmt = stmt.where(Category.direction == direction)
    if not include_statutory:
        stmt = stmt.where(Category.statutory.is_(False))
    return db.execute(stmt.order_by(Category.direction, Category.name)).scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    exists = db.execute(
        select(Category).where(
            Category.name == payload.name, Category.direction == payload.direction
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(409, "Category with this name and direction already exists")
    cat = Category(
        name=payload.name,
        direction=payload.direction,
        statutory=False,
        is_system=False,
        user_id=user.id,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ---------------------------------------------------------------- transactions


def _resolve_currency(payload_currency: str | None, region: Region | None, user: User) -> str:
    if payload_currency:
        return payload_currency.upper()
    if region is not None:
        return REGION_CURRENCY[region]
    return user.base_currency


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
    direction: TxDirection | None = None,
    limit: int = Query(500, le=2000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if start is not None:
        stmt = stmt.where(Transaction.occurred_on >= start)
    if end is not None:
        stmt = stmt.where(Transaction.occurred_on <= end)
    if region is not None:
        stmt = stmt.where(Transaction.region == region)
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)
    stmt = stmt.order_by(
        Transaction.occurred_on.desc(), Transaction.occurred_time.desc(), Transaction.id.desc()
    ).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/transactions/balances", response_model=TransactionBalancesResponse)
def transaction_balances(
    currency: str | None = None,
    region: Region | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Full-history cumulative balance per transaction — feeds the Ledger
    table's running-balance column."""
    ccy = (currency or user.base_currency).upper()
    balances = analytics_svc.running_balance_by_transaction(db, user.id, currency=ccy, region=region)
    return TransactionBalancesResponse(currency=ccy, balances=balances)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    category = db.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    if category.direction != payload.direction:
        raise HTTPException(422, "Category direction does not match transaction direction")

    tx = Transaction(
        user_id=user.id,
        direction=payload.direction,
        category_id=payload.category_id,
        amount=payload.amount,
        currency=_resolve_currency(payload.currency, payload.region, user),
        region=payload.region,
        occurred_on=payload.occurred_on,
        occurred_time=payload.occurred_time,
        description=payload.description,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.patch("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(
    tx_id: int,
    payload: TransactionUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    tx = db.get(Transaction, tx_id)
    if tx is None or tx.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tx, key, value)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    tx = db.get(Transaction, tx_id)
    if tx is None or tx.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    db.delete(tx)
    db.commit()
