"""Double-entry posting: the only module permitted to write journal tables.

Everything here exists to protect one invariant — **every entry's debits equal
its credits**. SQL cannot express that portably (it spans rows), so it is
enforced here and re-checked by :func:`integrity_check`. Routers call these
functions; they never construct :class:`JournalLine` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.base import AccountType, EntrySource
from app.models.journal import JournalEntry, JournalLine
from app.tax.models import money

ZERO = Decimal("0")


class JournalError(ValueError):
    """Any rejected posting. Routers translate this to HTTP 422."""


class UnbalancedEntry(JournalError):
    pass


@dataclass(frozen=True)
class LineInput:
    """One requested line. Exactly one of debit/credit must be positive."""

    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    memo: str | None = None


# --------------------------------------------------------------- validation


def _load_accounts(db: Session, user_id: int, account_ids: set[int]) -> dict[int, Account]:
    rows = (
        db.execute(select(Account).where(Account.id.in_(account_ids))).scalars().all()
        if account_ids
        else []
    )
    found = {a.id: a for a in rows if a.user_id == user_id}
    missing = account_ids - found.keys()
    if missing:
        raise JournalError(f"Unknown account id(s): {sorted(missing)}")
    archived = [a.code for a in found.values() if a.archived_at is not None or not a.is_active]
    if archived:
        raise JournalError(f"Cannot post to archived account(s): {', '.join(sorted(archived))}")
    return found


def validate_lines(db: Session, user_id: int, lines: list[LineInput]) -> dict[int, Account]:
    """Check the posting rules and return the accounts involved.

    Raises :class:`JournalError` (or :class:`UnbalancedEntry`) rather than
    returning a flag — an invalid posting has no partially-useful outcome.
    """
    if len(lines) < 2:
        raise JournalError("A journal entry needs at least two lines")

    debits = ZERO
    credits = ZERO
    for i, line in enumerate(lines, start=1):
        debit = money(line.debit or ZERO)
        credit = money(line.credit or ZERO)
        if debit < 0 or credit < 0:
            raise JournalError(f"Line {i}: amounts cannot be negative")
        if debit > 0 and credit > 0:
            raise JournalError(f"Line {i}: a line is either a debit or a credit, not both")
        if debit == 0 and credit == 0:
            raise JournalError(f"Line {i}: a line must carry an amount")
        debits += debit
        credits += credit

    if money(debits) != money(credits):
        raise UnbalancedEntry(
            f"Entry does not balance: debits {money(debits)} vs credits {money(credits)}"
        )

    return _load_accounts(db, user_id, {line.account_id for line in lines})


# ------------------------------------------------------------------ posting


def post_entry(
    db: Session,
    user_id: int,
    *,
    occurred_at: datetime,
    lines: list[LineInput],
    memo: str | None = None,
    payee_id: int | None = None,
    source: EntrySource = EntrySource.MANUAL,
    source_ref: str | None = None,
    reverses_id: int | None = None,
    commit: bool = True,
) -> JournalEntry:
    """Validate and persist one balanced entry."""
    validate_lines(db, user_id, lines)

    entry = JournalEntry(
        user_id=user_id,
        occurred_at=occurred_at,
        memo=memo,
        payee_id=payee_id,
        source=source,
        source_ref=source_ref,
        reverses_id=reverses_id,
    )
    entry.lines = [
        JournalLine(
            line_no=i,
            account_id=line.account_id,
            debit=money(line.debit or ZERO),
            credit=money(line.credit or ZERO),
            memo=line.memo,
        )
        for i, line in enumerate(lines, start=1)
    ]
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def update_entry(
    db: Session,
    user_id: int,
    entry_id: int,
    *,
    occurred_at: datetime | None = None,
    lines: list[LineInput] | None = None,
    memo: str | None = None,
    payee_id: int | None = None,
    clear_payee: bool = False,
) -> JournalEntry:
    """Amend an entry in place, replacing its whole line set if lines are given.

    Lines are replaced wholesale rather than patched individually: a partial
    line edit can transiently unbalance the entry, and there is no meaningful
    identity to a line beyond its position within its entry.
    """
    entry = get_entry(db, user_id, entry_id)
    if entry.voided_at is not None:
        raise JournalError("Cannot amend a voided entry")

    if lines is not None:
        validate_lines(db, user_id, lines)
        # Delete the old lines and flush before adding the new ones. Assigning
        # the collection in one step lets SQLAlchemy order the INSERTs before
        # the DELETEs, which collides on the (entry_id, line_no) unique index
        # whenever the replacement set reuses an ordinal — that is, always.
        entry.lines.clear()
        db.flush()
        entry.lines = [
            JournalLine(
                line_no=i,
                account_id=line.account_id,
                debit=money(line.debit or ZERO),
                credit=money(line.credit or ZERO),
                memo=line.memo,
            )
            for i, line in enumerate(lines, start=1)
        ]
    if occurred_at is not None:
        entry.occurred_at = occurred_at
    if memo is not None:
        entry.memo = memo
    if clear_payee:
        entry.payee_id = None
    elif payee_id is not None:
        entry.payee_id = payee_id

    db.commit()
    db.refresh(entry)
    return entry


def void_entry(db: Session, user_id: int, entry_id: int) -> JournalEntry:
    """Soft-delete: the row survives so the ledger stays auditable."""
    entry = get_entry(db, user_id, entry_id)
    if entry.voided_at is None:
        entry.voided_at = datetime.utcnow()
        db.commit()
        db.refresh(entry)
    return entry


def get_entry(db: Session, user_id: int, entry_id: int) -> JournalEntry:
    entry = db.get(JournalEntry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise LookupError(f"Journal entry {entry_id} not found")
    return entry


# ------------------------------------------------------- convenience posting

#: The kinds the quick-entry form offers, and the account types each side must
#: hold. `income` credits an income account and debits where the money landed;
#: `expense` debits an expense account and credits where it came from;
#: `transfer` moves between two balance-sheet accounts and touches neither.
_STOCK = (AccountType.ASSET, AccountType.LIABILITY)


def simple_entry(
    db: Session,
    user_id: int,
    *,
    kind: str,
    amount: Decimal,
    account_id: int,
    counter_account_id: int,
    occurred_at: datetime,
    memo: str | None = None,
    payee_id: int | None = None,
) -> JournalEntry:
    """Build and post the two-line entry behind "money in / out / transfer".

    `account_id` is always the balance-sheet side (where the money landed or
    came from); `counter_account_id` is the income or expense account, or the
    other balance-sheet account for a transfer.
    """
    value = money(amount)
    if value <= 0:
        raise JournalError("Amount must be greater than zero")
    if account_id == counter_account_id:
        raise JournalError("An entry cannot post both sides to the same account")

    accounts = _load_accounts(db, user_id, {account_id, counter_account_id})
    money_side = accounts[account_id]
    other = accounts[counter_account_id]

    if money_side.type not in _STOCK:
        raise JournalError(
            f"{money_side.code} {money_side.name} is a {money_side.type.value} account; "
            "the money side must be an asset or liability"
        )

    if kind == "income":
        if other.type is not AccountType.INCOME:
            raise JournalError(f"{other.code} {other.name} is not an income account")
        lines = [
            LineInput(account_id=account_id, debit=value),
            LineInput(account_id=counter_account_id, credit=value),
        ]
        source = EntrySource.MANUAL
    elif kind == "expense":
        if other.type is not AccountType.EXPENSE:
            raise JournalError(f"{other.code} {other.name} is not an expense account")
        lines = [
            LineInput(account_id=counter_account_id, debit=value),
            LineInput(account_id=account_id, credit=value),
        ]
        source = EntrySource.MANUAL
    elif kind == "transfer":
        if other.type not in _STOCK:
            raise JournalError(
                f"{other.code} {other.name} is a {other.type.value} account; a transfer "
                "moves between two asset or liability accounts"
            )
        # Debit the destination, credit the source. `account_id` is the
        # destination so the parameter keeps its "where the money landed" sense.
        lines = [
            LineInput(account_id=account_id, debit=value),
            LineInput(account_id=counter_account_id, credit=value),
        ]
        source = EntrySource.TRANSFER
    else:
        raise JournalError(f"Unknown entry kind {kind!r}; expected income, expense or transfer")

    return post_entry(
        db,
        user_id,
        occurred_at=occurred_at,
        lines=lines,
        memo=memo,
        payee_id=payee_id,
        source=source,
    )


def is_transfer(entry: JournalEntry, accounts: dict[int, Account]) -> bool:
    """True when no line touches an income or expense account.

    This is the definition that keeps savings out of the spending figures: a
    move from a payroll account into savings is a transfer, not an expense.
    """
    return all(
        accounts[line.account_id].type not in (AccountType.INCOME, AccountType.EXPENSE)
        for line in entry.lines
    )


# ------------------------------------------------------------ integrity


@dataclass(frozen=True)
class Problem:
    entry_id: int | None
    kind: str
    detail: str


def integrity_check(db: Session, user_id: int) -> list[Problem]:
    """Re-verify the invariants across the whole journal.

    Used by tests and by /warehouse/status, so a drifted or hand-edited
    database reports itself instead of quietly producing wrong analytics.
    """
    problems: list[Problem] = []
    entries = (
        db.execute(select(JournalEntry).where(JournalEntry.user_id == user_id)).scalars().all()
    )
    accounts = {a.id: a for a in db.execute(select(Account)).scalars().all()}

    for entry in entries:
        if not entry.lines:
            problems.append(Problem(entry.id, "empty_entry", "Entry has no lines"))
            continue
        debits = money(sum((line.debit for line in entry.lines), ZERO))
        credits = money(sum((line.credit for line in entry.lines), ZERO))
        if debits != credits:
            problems.append(
                Problem(entry.id, "unbalanced", f"debits {debits} != credits {credits}")
            )
        if len(entry.lines) < 2:
            problems.append(Problem(entry.id, "single_line", "Entry has fewer than two lines"))
        for line in entry.lines:
            if line.account_id not in accounts:
                problems.append(
                    Problem(
                        entry.id,
                        "orphan_line",
                        f"Line posts to missing account {line.account_id}",
                    )
                )
    return problems
