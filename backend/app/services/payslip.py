"""Post a computed payslip to the ledger as one multi-line journal entry.

This is where F1 (the tax engine) and F2 (the ledger) finally meet: a payslip
is not one movement but several — gross earned, each statutory deduction
withheld, and the remainder landing in a bank account — and double entry is
what lets a single balanced entry say all of that at once.

    DR 6020 SSS                1,125.00
    DR 6030 PhilHealth           625.00
    DR 6040 Pag-IBIG             100.00
    DR 6010 Income tax         2,708.33
    DR 1020 Bank - payroll    20,441.67   <- net take-home
                    CR 4010 Base salary          25,000.00
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.base import AccountType, EntrySource
from app.models.journal import JournalEntry
from app.models.salary import SalaryProfile
from app.services.journal import JournalError, LineInput, post_entry
from app.tax.models import money

ZERO = Decimal("0")

#: Maps a breakdown line-item key to the account code it posts against. The
#: keys come from app/tax/regions/ph.py; the codes from the seeded chart.
DEDUCTION_ACCOUNTS: dict[str, str] = {
    "sss": "6020",
    "philhealth": "6030",
    "pagibig": "6040",
    "income_tax": "6010",
}
GROSS_INCOME_CODE = "4010"  # Base salary


def _account_by_code(db: Session, user_id: int, code: str) -> Account:
    account = db.execute(
        select(Account).where(Account.user_id == user_id, Account.code == code)
    ).scalar_one_or_none()
    if account is None:
        raise JournalError(f"Chart of accounts is missing account {code}; re-run the seed")
    return account


def existing_posting(db: Session, user_id: int, profile_id: int) -> JournalEntry | None:
    """The entry a previous post produced for this profile, if any."""
    return db.execute(
        select(JournalEntry).where(
            JournalEntry.user_id == user_id,
            JournalEntry.source == EntrySource.PAYSLIP,
            JournalEntry.source_ref == str(profile_id),
        )
    ).scalar_one_or_none()


def post_payslip(
    db: Session,
    user_id: int,
    profile: SalaryProfile,
    *,
    deposit_account_id: int,
    occurred_at: datetime | None = None,
) -> tuple[JournalEntry, bool]:
    """Post `profile`'s breakdown as a journal entry.

    Returns `(entry, created)`. Re-posting the same profile is a no-op — the
    unique (user, source, source_ref) constraint makes that guarantee
    structural rather than a race-prone check, and the caller gets the
    original entry back.
    """
    existing = existing_posting(db, user_id, profile.id)
    if existing is not None:
        return existing, False

    breakdown = profile.breakdown or {}
    items = breakdown.get("items", [])
    if not items:
        raise JournalError("Salary profile has no computed breakdown to post")

    def period_amount(item: dict) -> Decimal:
        # `amount_period` is written by Breakdown.to_dict; fall back to the
        # annual figure for any snapshot saved before that field existed.
        return money(item.get("amount_period", item.get("amount", "0")))

    by_key = {item["key"]: item for item in items}

    gross = period_amount(by_key["gross"]) if "gross" in by_key else ZERO
    net = period_amount(by_key["net"]) if "net" in by_key else ZERO
    if gross <= 0:
        raise JournalError("Salary profile has a zero gross; nothing to post")

    deposit = db.get(Account, deposit_account_id)
    if deposit is None or deposit.user_id != user_id:
        raise JournalError(f"Unknown deposit account {deposit_account_id}")
    if deposit.type is not AccountType.ASSET:
        raise JournalError(
            f"{deposit.code} {deposit.name} is a {deposit.type.value} account; "
            "net pay must land in an asset account"
        )

    lines: list[LineInput] = []
    deductions_total = ZERO
    for key, code in DEDUCTION_ACCOUNTS.items():
        item = by_key.get(key)
        if item is None:
            continue
        amount = period_amount(item)
        if amount <= 0:
            continue
        account = _account_by_code(db, user_id, code)
        lines.append(LineInput(account_id=account.id, debit=amount, memo=item.get("label")))
        deductions_total += amount

    # Derive the deposit from what actually posted rather than trusting the
    # snapshot's net line: if a deduction key is missing from the chart, the
    # entry must still balance, and the difference belongs in the bank.
    deposit_amount = money(gross - deductions_total)
    if deposit_amount <= 0:
        raise JournalError("Deductions equal or exceed gross; refusing to post")
    lines.append(
        LineInput(account_id=deposit.id, debit=deposit_amount, memo="Net take-home")
    )

    income_account = _account_by_code(db, user_id, GROSS_INCOME_CODE)
    lines.append(
        LineInput(account_id=income_account.id, credit=gross, memo="Gross salary")
    )

    label = profile.label or "Salary"
    memo = f"{label} · payslip"
    if net and net != deposit_amount:
        memo += f" (snapshot net {net})"

    entry = post_entry(
        db,
        user_id,
        occurred_at=occurred_at or datetime.utcnow(),
        lines=lines,
        memo=memo,
        source=EntrySource.PAYSLIP,
        source_ref=str(profile.id),
    )
    return entry, True
