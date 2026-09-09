"""Chart of accounts — the dimension every posting resolves against."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.account import Account
from app.models.base import CURRENCY, AccountType
from app.models.user import User
from app.schemas import (
    AccountBalanceOut,
    AccountBalancesResponse,
    AccountCreate,
    AccountOut,
    AccountUpdate,
)
from app.services import balances as balances_svc
from app.tax.models import money
from app.warehouse import etl

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    include_archived: bool = False,
    type: AccountType | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Account).where(Account.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    if type is not None:
        stmt = stmt.where(Account.type == type)
    return db.execute(stmt.order_by(Account.code)).scalars().all()


@router.get("/balances", response_model=AccountBalancesResponse)
def account_balances(
    as_of: datetime | None = None,
    include_archived: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = balances_svc.account_balances(
        db, user.id, as_of=as_of, include_archived=include_archived
    )
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        totals[row.type.value] += row.balance

    assets = totals.get(AccountType.ASSET.value, Decimal("0"))
    liabilities = totals.get(AccountType.LIABILITY.value, Decimal("0"))

    return AccountBalancesResponse(
        currency=CURRENCY,
        as_of=as_of,
        accounts=[AccountBalanceOut(**vars(r)) for r in rows],
        totals_by_type={k: money(v) for k, v in totals.items()},
        # Liabilities are credit-normal, so a positive balance is money owed.
        net_worth=money(assets - liabilities),
    )


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    account = Account(
        user_id=user.id,
        code=payload.code,
        name=payload.name,
        type=payload.type,
        subtype=payload.subtype,
        opening_balance=payload.opening_balance,
        is_system=False,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"Account code {payload.code} already exists") from exc
    db.refresh(account)
    _sync_dimension(db)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    account = _owned(db, user, account_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    _sync_dimension(db)
    return account


@router.delete("/{account_id}", status_code=204)
def archive_account(
    account_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Archive rather than delete.

    An account with postings can never be removed: historical entries would
    lose the meaning of their lines. Archiving hides it from pickers while
    keeping every past entry readable.
    """
    account = _owned(db, user, account_id)
    if account.is_system and balances_svc.has_postings(db, account_id):
        raise HTTPException(409, "A seeded account with postings cannot be removed, only archived")
    account.archived_at = datetime.utcnow()
    account.is_active = False
    db.commit()
    _sync_dimension(db)


def _owned(db: Session, user: User, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Account not found")
    return account


def _sync_dimension(db: Session) -> None:
    """Push the chart into dim_account so analytics labels stay current."""
    try:
        from app.warehouse.engine import cursor

        with cursor() as conn:
            etl.sync_accounts(db, conn)
    except Exception:  # a stale label must not fail a chart edit
        etl.mark_stale("dim_account sync failed")
