"""Account balances derived from journal lines.

An account's balance is its opening balance plus every posting, signed by the
type's normal balance: assets and expenses grow on the debit side, liabilities,
equity and income on the credit side. Voided entries never count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.base import DEBIT_NORMAL, AccountType
from app.models.journal import JournalEntry, JournalLine
from app.tax.models import money

ZERO = Decimal("0")


@dataclass
class AccountBalance:
    account_id: int
    code: str
    name: str
    type: AccountType
    subtype: str | None
    is_active: bool
    debits: Decimal
    credits: Decimal
    balance: Decimal


def _posting_totals(
    db: Session, user_id: int, *, as_of: datetime | None = None
) -> dict[int, tuple[Decimal, Decimal]]:
    """(debits, credits) per account across all non-voided entries."""
    stmt: Select = (
        select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.user_id == user_id, JournalEntry.voided_at.is_(None))
        .group_by(JournalLine.account_id)
    )
    if as_of is not None:
        stmt = stmt.where(JournalEntry.occurred_at <= as_of)
    return {
        account_id: (Decimal(str(debits)), Decimal(str(credits)))
        for account_id, debits, credits in db.execute(stmt).all()
    }


def signed_balance(account_type: AccountType, debits: Decimal, credits: Decimal) -> Decimal:
    """Net the two sides in the direction the account naturally grows."""
    if account_type in DEBIT_NORMAL:
        return money(debits - credits)
    return money(credits - debits)


def account_balances(
    db: Session,
    user_id: int,
    *,
    as_of: datetime | None = None,
    include_archived: bool = False,
) -> list[AccountBalance]:
    totals = _posting_totals(db, user_id, as_of=as_of)
    stmt = select(Account).where(Account.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    accounts = db.execute(stmt.order_by(Account.code)).scalars().all()

    out: list[AccountBalance] = []
    for account in accounts:
        debits, credits = totals.get(account.id, (ZERO, ZERO))
        out.append(
            AccountBalance(
                account_id=account.id,
                code=account.code,
                name=account.name,
                type=account.type,
                subtype=account.subtype,
                is_active=account.is_active,
                debits=money(debits),
                credits=money(credits),
                balance=signed_balance(account.type, debits, credits),
            )
        )
    return out


def has_postings(db: Session, account_id: int) -> bool:
    """Whether any line — voided or not — references this account."""
    return (
        db.execute(
            select(func.count())
            .select_from(JournalLine)
            .where(JournalLine.account_id == account_id)
        ).scalar_one()
        > 0
    )
