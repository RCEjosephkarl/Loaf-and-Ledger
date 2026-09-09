"""Double-entry journal: entries and their balanced debit/credit lines.

The invariant that makes this a ledger rather than a list — every entry's
debits equal its credits — cannot be expressed as a portable table CHECK, so it
is enforced in :mod:`app.services.journal`, which is the only module permitted
to write these tables. The per-line CHECKs below cover what SQL *can* say: no
negative amounts, and every line is exactly one side of the ledger.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, EntrySource, Money


class JournalEntry(Base):
    """One economic event. Carries no amount of its own — the amount lives in
    the lines, and the entry is only meaningful as the set of them."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        Index("ix_entry_user_occurred", "user_id", "occurred_at"),
        Index("ix_entry_user_source", "user_id", "source"),
        Index("ix_entry_user_voided", "user_id", "voided_at"),
        # Idempotency for machine-generated postings: a given payslip profile
        # posts at most once. NULL source_ref repeats freely (manual entries).
        UniqueConstraint("user_id", "source", "source_ref", name="uq_entry_source_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Date *and* time in one column. The previous schema split these into a
    # date plus a nullable time, which forced a `time or time.min` coalesce at
    # every sort site; a single non-null timestamp removes the special case.
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_id: Mapped[int | None] = mapped_column(ForeignKey("payees.id"), nullable=True)

    source: Mapped[EntrySource] = mapped_column(
        Enum(EntrySource), default=EntrySource.MANUAL, nullable=False
    )
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Set when this entry was posted to reverse another, keeping both halves of
    # a correction visible instead of rewriting history.
    reverses_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # Soft delete — a ledger you can silently erase rows from is not auditable.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lines: Mapped[list[JournalLine]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_no",
        lazy="selectin",
    )

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None


class JournalLine(Base):
    """One side of one entry: an amount posted to an account as debit or credit."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_line_non_negative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_line_single_sided"),
        CheckConstraint("debit > 0 OR credit > 0", name="ck_line_non_zero"),
        UniqueConstraint("entry_id", "line_no", name="uq_line_ordinal"),
        Index("ix_line_account", "account_id"),
        Index("ix_line_entry", "entry_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)

    debit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")

    @property
    def amount(self) -> Decimal:
        """The line's magnitude, whichever side it sits on."""
        return self.debit if self.debit else self.credit
