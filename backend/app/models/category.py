"""Transaction categories: system-seeded + user custom, in/out, statutory flag."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Region, TxDirection


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "direction", name="uq_category_name_direction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    direction: Mapped[TxDirection] = mapped_column(Enum(TxDirection))
    # Statutory = mandatory salary deduction owned by the tax engine (F1),
    # kept distinct from discretionary spend so analytics (F3) stays clean.
    statutory: Mapped[bool] = mapped_column(Boolean, default=False)
    # NULL region = global; otherwise the region this statutory item belongs to.
    region: Mapped[Region | None] = mapped_column(Enum(Region), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set for user-created categories (local single user).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
