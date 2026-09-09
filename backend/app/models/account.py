"""Chart of accounts — the dimension every journal line posts against."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AccountType, Base, Money


class Account(Base):
    """One line of the chart of accounts.

    `code` is the human-facing account number (1010, 4010, 6020…) and carries
    the convention that the leading digit encodes the type — assets 1xxx,
    liabilities 2xxx, equity 3xxx, income 4xxx, expenses 5xxx/6xxx, with 6xxx
    reserved for statutory payroll deductions.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_account_code"),
        Index("ix_account_user_type", "user_id", "type"),
        Index("ix_account_user_active", "user_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    # Free-form grouping within a type: cash | bank | ewallet | card | loan |
    # statutory | discretionary. Drives icons and the Analytics groupings.
    subtype: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Statutory = a mandatory payroll deduction owned by the tax engine (F1),
    # kept distinct from discretionary spend so "where did it go" stays honest.
    is_statutory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Balance the account carried before the first journal entry. Posted as a
    # real opening entry against equity at seed time, so the journal alone is
    # always sufficient to reproduce a balance.
    opening_balance: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # Archived rather than deleted: an account with postings must stay
    # resolvable forever, or historical entries lose their meaning.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
