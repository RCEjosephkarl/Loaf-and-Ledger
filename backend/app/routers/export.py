"""F5 — server-generated CSV export of expenses (streamed, stdlib csv)."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import Region, TxDirection
from app.models.fx import ExchangeRateHistory
from app.models.transaction import Transaction
from app.models.user import User
from app.services.analytics import category_map
from app.services.currency import convert

router = APIRouter(prefix="/export", tags=["export"])


def _rows(db: Session, user: User, start, end, region, direction, display_currency):
    cats = category_map(db)
    stmt = select(Transaction).where(
        Transaction.user_id == user.id, Transaction.direction == direction
    )
    if start is not None:
        stmt = stmt.where(Transaction.occurred_on >= start)
    if end is not None:
        stmt = stmt.where(Transaction.occurred_on <= end)
    if region is not None:
        stmt = stmt.where(Transaction.region == region)
    stmt = stmt.order_by(Transaction.occurred_on)

    header = ["date", "category", "direction", "amount", "currency", "region", "description"]
    if display_currency:
        header += [f"amount_{display_currency.upper()}"]
    yield header

    for tx in db.execute(stmt).scalars():
        row = [
            tx.occurred_on.isoformat(),
            cats.get(tx.category_id).name if tx.category_id in cats else "Uncategorized",
            tx.direction.value,
            f"{Decimal(str(tx.amount)):.2f}",
            tx.currency,
            tx.region.value if tx.region else "",
            tx.description or "",
        ]
        if display_currency:
            row.append(
                f"{convert(db, Decimal(str(tx.amount)), tx.currency, display_currency.upper()):.2f}"
            )
        yield row


@router.get("/expenses.csv")
def export_expenses(
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
    currency: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream expenses as CSV. Optional `currency` adds a converted-amount column."""

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in _rows(db, user, start, end, region, TxDirection.OUTBOUND, currency):
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"expenses_{datetime.utcnow():%Y%m%d}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/fx-rates.csv")
def export_fx_rates(
    base: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the cached FX rate history as CSV — separate from expenses.csv
    since it's a currency time series, not a ledger of transactions."""
    ccy = (base or user.base_currency).upper()

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["date", "base_currency", "quote_currency", "rate"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        # Executed lazily, once this generator is actually iterated during
        # streaming — matching `_rows()` above. Executing the query eagerly
        # (before returning the response) reads from a cursor after the
        # request-scoped session has moved on, which SQLAlchemy rejects.
        stmt = (
            select(ExchangeRateHistory)
            .where(ExchangeRateHistory.base_currency == ccy)
            .order_by(ExchangeRateHistory.as_of, ExchangeRateHistory.quote_currency)
        )
        for r in db.execute(stmt).scalars():
            rate = f"{Decimal(str(r.rate)):.6f}"
            writer.writerow([r.as_of.isoformat(), r.base_currency, r.quote_currency, rate])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"fx_rates_{ccy}_{datetime.utcnow():%Y%m%d}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
