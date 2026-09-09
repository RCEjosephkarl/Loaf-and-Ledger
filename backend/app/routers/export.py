"""F5 — server-generated CSV export of the ledger (streamed, stdlib csv)."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.account import Account
from app.models.base import CURRENCY
from app.models.journal import JournalEntry, JournalLine
from app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])

HEADER = [
    "entry_id",
    "occurred_at",
    "source",
    "memo",
    "line_no",
    "account_code",
    "account_name",
    "account_type",
    "debit",
    "credit",
    "currency",
]


def _rows(db: Session, user: User, start: date | None, end: date | None, account_id: int | None):
    """One row per journal line — the export granularity that keeps a
    double-entry ledger reconstructable from the CSV alone."""
    accounts = {a.id: a for a in db.execute(select(Account)).scalars()}

    stmt = (
        select(JournalEntry)
        .where(JournalEntry.user_id == user.id, JournalEntry.voided_at.is_(None))
        .order_by(JournalEntry.occurred_at, JournalEntry.id)
    )
    if start is not None:
        stmt = stmt.where(JournalEntry.occurred_at >= datetime.combine(start, time.min))
    if end is not None:
        stmt = stmt.where(JournalEntry.occurred_at <= datetime.combine(end, time.max))
    if account_id is not None:
        stmt = stmt.where(
            JournalEntry.id.in_(
                select(JournalLine.entry_id).where(JournalLine.account_id == account_id)
            )
        )

    yield HEADER
    for entry in db.execute(stmt).scalars():
        for line in entry.lines:
            account = accounts.get(line.account_id)
            yield [
                entry.id,
                entry.occurred_at.isoformat(sep=" ", timespec="minutes"),
                entry.source.value,
                entry.memo or "",
                line.line_no,
                account.code if account else "",
                account.name if account else "Unknown",
                account.type.value if account else "",
                f"{Decimal(str(line.debit)):.2f}",
                f"{Decimal(str(line.credit)):.2f}",
                CURRENCY,
            ]


@router.get("/ledger.csv")
def export_ledger(
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the journal as CSV, one row per line."""

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in _rows(db, user, start, end, account_id):
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"ledger_{datetime.utcnow():%Y%m%d}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trial-balance.csv")
def export_trial_balance(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    """Stream a trial balance — every account's debit and credit totals.

    The classic proof that a double-entry ledger is sound: the two columns
    must sum to the same figure. Only possible now that the schema is
    genuinely double-entry.
    """
    from app.services import balances as balances_svc

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["code", "name", "type", "debits", "credits", "balance", "currency"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for row in balances_svc.account_balances(db, user.id, include_archived=True):
            total_debits += row.debits
            total_credits += row.credits
            writer.writerow(
                [
                    row.code,
                    row.name,
                    row.type.value,
                    f"{row.debits:.2f}",
                    f"{row.credits:.2f}",
                    f"{row.balance:.2f}",
                    CURRENCY,
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

        writer.writerow(
            ["", "TOTAL", "", f"{total_debits:.2f}", f"{total_credits:.2f}", "", CURRENCY]
        )
        yield buffer.getvalue()

    filename = f"trial_balance_{datetime.utcnow():%Y%m%d}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
