"""F2 — the ledger: double-entry journal CRUD.

Every mutation here follows the same shape: commit to the OLTP journal, then
write through to the warehouse so analytics are coherent before the response
returns. The warehouse write is deliberately allowed to fail without failing
the ledger write — see `etl.safe_apply_entry`.
"""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import current_user
from app.models.account import Account
from app.models.base import AccountType, EntrySource
from app.models.journal import JournalEntry, JournalLine
from app.models.user import User
from app.schemas import (
    JournalEntryCreate,
    JournalEntryOut,
    JournalEntryPage,
    JournalEntryUpdate,
    JournalEntryWithBalance,
    SimpleEntryCreate,
)
from app.services import journal as journal_svc
from app.tax.models import money
from app.warehouse import etl

router = APIRouter(prefix="/ledger", tags=["ledger"])


def _line_inputs(lines) -> list[journal_svc.LineInput]:  # noqa: ANN001
    return [
        journal_svc.LineInput(
            account_id=line.account_id, debit=line.debit, credit=line.credit, memo=line.memo
        )
        for line in lines
    ]


@router.get("/entries", response_model=list[JournalEntryOut])
def list_entries(
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    source: EntrySource | None = None,
    include_voided: bool = False,
    limit: int = Query(500, le=2000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if not include_voided:
        stmt = stmt.where(JournalEntry.voided_at.is_(None))
    if start is not None:
        stmt = stmt.where(JournalEntry.occurred_at >= datetime.combine(start, time.min))
    if end is not None:
        stmt = stmt.where(JournalEntry.occurred_at <= datetime.combine(end, time.max))
    if source is not None:
        stmt = stmt.where(JournalEntry.source == source)
    if account_id is not None:
        # Match the whole entry, not the single line: an expense paid from a
        # card should still show both of its sides when filtered by the card.
        stmt = stmt.where(
            JournalEntry.id.in_(
                select(JournalLine.entry_id).where(JournalLine.account_id == account_id)
            )
        )
    stmt = stmt.order_by(JournalEntry.occurred_at.desc(), JournalEntry.id.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/entries/page", response_model=JournalEntryPage)
def entry_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # Aggregate per entry before the window, so multi-line postings count once.
    activity = (
        select(
            JournalEntry.id.label("entry_id"),
            JournalEntry.occurred_at.label("occurred_at"),
            func.sum(JournalLine.debit).label("posted"),
            func.sum(
                case(
                    (Account.type == AccountType.ASSET, JournalLine.debit - JournalLine.credit),
                    else_=0,
                )
            ).label("cash_change"),
        )
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.user_id == user.id, JournalEntry.voided_at.is_(None))
        .group_by(JournalEntry.id, JournalEntry.occurred_at)
        .subquery()
    )
    total, posted_total = db.execute(
        select(func.count(), func.coalesce(func.sum(activity.c.posted), 0)).select_from(activity)
    ).one()
    running = select(
        activity.c.entry_id,
        activity.c.occurred_at,
        func.sum(activity.c.cash_change)
        .over(order_by=(activity.c.occurred_at, activity.c.entry_id), rows=(None, 0))
        .label("cash_balance"),
    ).subquery()
    rows = db.execute(
        select(JournalEntry, running.c.cash_balance)
        .join(running, running.c.entry_id == JournalEntry.id)
        .options(selectinload(JournalEntry.lines))
        .order_by(running.c.occurred_at.desc(), running.c.entry_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return JournalEntryPage(
        items=[
            JournalEntryWithBalance(
                **JournalEntryOut.model_validate(entry).model_dump(), cash_balance=money(balance)
            )
            for entry, balance in rows
        ],
        total=total,
        posted_total=money(posted_total),
        page=page,
        page_size=page_size,
    )


@router.get("/entries/{entry_id}", response_model=JournalEntryOut)
def get_entry(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return journal_svc.get_entry(db, user.id, entry_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/entries", response_model=JournalEntryOut, status_code=201)
def create_entry(
    payload: JournalEntryCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Post a full multi-line journal entry."""
    try:
        entry = journal_svc.post_entry(
            db,
            user.id,
            occurred_at=payload.occurred_at,
            lines=_line_inputs(payload.lines),
            memo=payload.memo,
            payee_id=payload.payee_id,
        )
    except journal_svc.JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    etl.safe_apply_entry(db, entry.id)
    return entry


@router.post("/entries/simple", response_model=JournalEntryOut, status_code=201)
def create_simple_entry(
    payload: SimpleEntryCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Quick entry: money in, money out, or a transfer between own accounts."""
    try:
        entry = journal_svc.simple_entry(
            db,
            user.id,
            kind=payload.kind,
            amount=payload.amount,
            account_id=payload.account_id,
            counter_account_id=payload.counter_account_id,
            occurred_at=payload.occurred_at,
            memo=payload.memo,
            payee_id=payload.payee_id,
        )
    except journal_svc.JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    etl.safe_apply_entry(db, entry.id)
    return entry


@router.patch("/entries/{entry_id}", response_model=JournalEntryOut)
def update_entry(
    entry_id: int,
    payload: JournalEntryUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    try:
        entry = journal_svc.update_entry(
            db,
            user.id,
            entry_id,
            occurred_at=payload.occurred_at,
            lines=_line_inputs(payload.lines) if payload.lines is not None else None,
            memo=payload.memo,
            payee_id=payload.payee_id,
            clear_payee="payee_id" in data and payload.payee_id is None,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except journal_svc.JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    etl.safe_apply_entry(db, entry.id)
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def void_entry(entry_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Void an entry. The row survives — a ledger you can silently erase from
    is not auditable — but it leaves every balance and every analytic."""
    try:
        journal_svc.void_entry(db, user.id, entry_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    etl.safe_apply_entry(db, entry_id)
