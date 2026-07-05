"""Currency conversion over the static exchange-rate table (display-only convert).

Amounts are always stored in their native currency; this converts for display.
Rates are stored as directed pairs (1 base = rate quote). Conversion tries a direct
pair, then the inverse, then a USD pivot.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fx import ExchangeRate
from app.tax.models import money

PIVOT = "USD"


def _rate(db: Session, base: str, quote: str) -> Decimal | None:
    if base == quote:
        return Decimal("1")
    direct = db.execute(
        select(ExchangeRate).where(
            ExchangeRate.base_currency == base, ExchangeRate.quote_currency == quote
        )
    ).scalar_one_or_none()
    if direct is not None:
        return Decimal(str(direct.rate))
    inverse = db.execute(
        select(ExchangeRate).where(
            ExchangeRate.base_currency == quote, ExchangeRate.quote_currency == base
        )
    ).scalar_one_or_none()
    if inverse is not None and Decimal(str(inverse.rate)) != 0:
        return Decimal("1") / Decimal(str(inverse.rate))
    return None


def get_rate(db: Session, base: str, quote: str) -> Decimal:
    """Return the conversion rate base->quote, via direct/inverse/USD pivot."""
    direct = _rate(db, base, quote)
    if direct is not None:
        return direct
    base_to_pivot = _rate(db, base, PIVOT)
    pivot_to_quote = _rate(db, PIVOT, quote)
    if base_to_pivot is not None and pivot_to_quote is not None:
        return base_to_pivot * pivot_to_quote
    raise ValueError(f"No exchange rate available for {base}->{quote}")


def convert(db: Session, amount: Decimal, base: str, quote: str) -> Decimal:
    """Convert an amount from `base` currency to `quote`, rounded to cents."""
    if base == quote:
        return money(amount)
    return money(Decimal(str(amount)) * get_rate(db, base, quote))
