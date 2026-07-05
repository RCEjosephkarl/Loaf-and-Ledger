"""Ledger transactions — categorized inbound/outbound money (F2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, Region, TxDirection


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    direction: Mapped[TxDirection] = mapped_column(Enum(TxDirection))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    # Stored in its native currency; converted for display (F6 currency switch).
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    region: Mapped[Region | None] = mapped_column(Enum(Region), nullable=True)

    occurred_on: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
