"""Per-category monthly budgets (F4) and period-level fund overrides."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BudgetScope, Money

# Sentinel period_start for scope=ALL, which has no natural period boundary —
# there is only ever one all-time fund override per user, so a fixed value is
# enough to satisfy the uniqueness constraint below.
FUND_ALL_SENTINEL = date(1970, 1, 1)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "year", "month", name="uq_budget_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)  # 1-12
    limit_amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))


class FundOverride(Base):
    """User-declared "initial fund" for a budget period, overriding the
    computed carry-over default (see services/budgets.py)."""

    __tablename__ = "fund_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", "period_start", name="uq_fund_override_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scope: Mapped[BudgetScope] = mapped_column(Enum(BudgetScope))
    period_start: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
