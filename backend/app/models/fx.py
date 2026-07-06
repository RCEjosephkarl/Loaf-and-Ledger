"""Static exchange-rate table (seeded, manually refreshed — no external API)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Rate


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", name="uq_fx_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    # 1 base_currency = <rate> quote_currency
    rate: Mapped[Decimal] = mapped_column(Rate)
    as_of: Mapped[date] = mapped_column(Date)


class ExchangeRateHistory(Base):
    """Daily close-rate time series, fetched live from an external FX provider.

    Kept separate from `ExchangeRate` (which holds only the current rate used
    for display conversion) so the dashboard trend chart and CSV export have
    a real history without repeatedly hitting the external API.
    """

    __tablename__ = "exchange_rate_history"
    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "as_of", name="uq_fx_history_point"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Rate)
    as_of: Mapped[date] = mapped_column(Date)
