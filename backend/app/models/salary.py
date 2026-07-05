"""Persistent salary calculator input + computed breakdown snapshot (F1)."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONVariant, Money, Region


class PayPeriod(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SalaryProfile(Base):
    """A saved salary scenario. The active profile is the persistent F1 input."""

    __tablename__ = "salary_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(120), default="My salary")
    region: Mapped[Region] = mapped_column(Enum(Region))
    currency: Mapped[str] = mapped_column(String(3))
    gross_amount: Mapped[Decimal] = mapped_column(Money)
    pay_period: Mapped[PayPeriod] = mapped_column(Enum(PayPeriod), default=PayPeriod.MONTHLY)
    tax_year: Mapped[int] = mapped_column(Integer)

    # Computed at save time so history survives later rule changes.
    net_amount: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    total_deductions: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    # Full line-item breakdown (tax, each social contribution, net) as JSONB.
    breakdown: Mapped[dict] = mapped_column(JSONVariant, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
