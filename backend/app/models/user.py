"""Single-user profile (local deployment — one row)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Region


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Breadwinner")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Preferred display currency (F6 default); amounts are stored natively.
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    default_region: Mapped[Region] = mapped_column(Enum(Region), default=Region.US)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
