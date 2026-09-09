"""Idempotent seed: single user, PH chart of accounts, and a demo ledger.

Run with:  uv run python -m app.seed
Safe to run repeatedly — existing rows are left untouched.

The seed writes both stores: the OLTP journal first, then a full warehouse
load. DuckDB allows one writer per file, so the warehouse half cannot run while
an API server holds it — in that case the ledger is still seeded correctly and
the command says how to finish the job.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.account import Account
from app.models.base import AccountType, EntrySource
from app.models.budget import Budget
from app.models.journal import JournalEntry
from app.models.payee import Payee
from app.models.salary import PayPeriod, SalaryProfile
from app.services.journal import LineInput, post_entry
from app.services.user import get_single_user
from app.tax import engine

# (code, name, type, subtype, is_statutory)
#
# The leading digit encodes the type: assets 1xxx, liabilities 2xxx, equity
# 3xxx, income 4xxx, discretionary expenses 5xxx, statutory deductions 6xxx.
CHART: list[tuple[str, str, AccountType, str | None, bool]] = [
    ("1010", "Cash on hand", AccountType.ASSET, "cash", False),
    ("1020", "Bank — payroll", AccountType.ASSET, "bank", False),
    ("1030", "Bank — savings", AccountType.ASSET, "bank", False),
    ("1040", "E-wallet (GCash)", AccountType.ASSET, "ewallet", False),
    ("1090", "Investments", AccountType.ASSET, "investment", False),
    ("2010", "Credit card", AccountType.LIABILITY, "card", False),
    ("2020", "Personal loan", AccountType.LIABILITY, "loan", False),
    ("3000", "Opening balance equity", AccountType.EQUITY, None, False),
    ("4010", "Base salary", AccountType.INCOME, "salary", False),
    ("4020", "Overtime", AccountType.INCOME, "salary", False),
    ("4030", "Bonus / 13th month", AccountType.INCOME, "salary", False),
    ("4040", "Allowances", AccountType.INCOME, "salary", False),
    ("4050", "Freelance income", AccountType.INCOME, "sideline", False),
    ("4060", "Interest income", AccountType.INCOME, "passive", False),
    ("4070", "Dividends", AccountType.INCOME, "passive", False),
    ("4090", "Other income", AccountType.INCOME, None, False),
    ("5010", "Housing / rent", AccountType.EXPENSE, "discretionary", False),
    ("5020", "Utilities", AccountType.EXPENSE, "discretionary", False),
    ("5030", "Groceries", AccountType.EXPENSE, "discretionary", False),
    ("5040", "Dining out", AccountType.EXPENSE, "discretionary", False),
    ("5050", "Transport", AccountType.EXPENSE, "discretionary", False),
    ("5060", "Healthcare", AccountType.EXPENSE, "discretionary", False),
    ("5070", "Insurance", AccountType.EXPENSE, "discretionary", False),
    ("5080", "Education", AccountType.EXPENSE, "discretionary", False),
    ("5090", "Family & dependents", AccountType.EXPENSE, "discretionary", False),
    ("5100", "Entertainment", AccountType.EXPENSE, "discretionary", False),
    ("5110", "Shopping", AccountType.EXPENSE, "discretionary", False),
    ("5120", "Subscriptions", AccountType.EXPENSE, "discretionary", False),
    ("5130", "Travel", AccountType.EXPENSE, "discretionary", False),
    ("5140", "Charity / tithe", AccountType.EXPENSE, "discretionary", False),
    ("5150", "Debt interest", AccountType.EXPENSE, "discretionary", False),
    ("5900", "Miscellaneous", AccountType.EXPENSE, "discretionary", False),
    ("6010", "Income tax (BIR)", AccountType.EXPENSE, "statutory", True),
    ("6020", "SSS", AccountType.EXPENSE, "statutory", True),
    ("6030", "PhilHealth", AccountType.EXPENSE, "statutory", True),
    ("6040", "Pag-IBIG", AccountType.EXPENSE, "statutory", True),
]
# Deliberately absent: a "Savings & investment" *expense* account. Money moved
# into 1030 or 1090 is a transfer between assets, not spending — modelling it
# as an expense is what made the old savings rate wrong.

PAYEES = [
    ("Ayala Land Leasing", "5010"),
    ("Meralco", "5020"),
    ("SM Supermarket", "5030"),
    ("Jollibee", "5040"),
    ("Grab", "5050"),
    ("Mercury Drug", "5060"),
    ("Globe Telecom", "5120"),
]

OPENING_BALANCES = {"1010": "3500.00", "1020": "18000.00", "1030": "42000.00", "1040": "1200.00"}

MONTHLY_GROSS = Decimal("42000")


def seed_chart(db: Session, user_id: int) -> dict[str, Account]:
    existing = {
        a.code: a
        for a in db.execute(select(Account).where(Account.user_id == user_id)).scalars().all()
    }
    for code, name, type_, subtype, statutory in CHART:
        if code in existing:
            continue
        account = Account(
            user_id=user_id,
            code=code,
            name=name,
            type=type_,
            subtype=subtype,
            is_statutory=statutory,
            is_system=True,
        )
        db.add(account)
        existing[code] = account
    db.commit()
    return {
        a.code: a
        for a in db.execute(select(Account).where(Account.user_id == user_id)).scalars().all()
    }


def seed_payees(db: Session, user_id: int, chart: dict[str, Account]) -> dict[str, Payee]:
    existing = {
        p.name: p
        for p in db.execute(select(Payee).where(Payee.user_id == user_id)).scalars().all()
    }
    for name, code in PAYEES:
        if name in existing:
            continue
        payee = Payee(user_id=user_id, name=name, default_account_id=chart[code].id)
        db.add(payee)
        existing[name] = payee
    db.commit()
    return existing


def _month_start(base: date, months_back: int) -> date:
    idx = base.year * 12 + (base.month - 1) - months_back
    return date(idx // 12, idx % 12 + 1, 1)


def seed_demo(db: Session) -> None:
    user = get_single_user(db)
    chart = seed_chart(db, user.id)
    payees = seed_payees(db, user.id, chart)

    if db.execute(select(JournalEntry).where(JournalEntry.user_id == user.id)).scalars().first():
        db.commit()
        return

    today = date.today()
    this_month = today.replace(day=1)

    # --- Opening balances. Posted as a real balanced entry against equity, so
    # the journal alone reproduces every balance — no magic starting numbers.
    opening_lines = [
        LineInput(account_id=chart[code].id, debit=Decimal(amount), memo="Opening balance")
        for code, amount in OPENING_BALANCES.items()
    ]
    opening_total = sum((Decimal(v) for v in OPENING_BALANCES.values()), Decimal("0"))
    opening_lines.append(
        LineInput(account_id=chart["3000"].id, credit=opening_total, memo="Opening balance equity")
    )
    post_entry(
        db,
        user.id,
        occurred_at=datetime.combine(_month_start(this_month, 3), time(0, 0)),
        lines=opening_lines,
        memo="Opening balances",
        source=EntrySource.OPENING,
        source_ref="seed",
    )

    # --- Salary profile, computed by the PH tax engine.
    profile = db.execute(
        select(SalaryProfile).where(SalaryProfile.user_id == user.id)
    ).scalars().first()
    if profile is None:
        breakdown = engine.compute(MONTHLY_GROSS, pay_period="monthly", year=2025)
        profile = SalaryProfile(
            user_id=user.id,
            label="Day job",
            gross_amount=MONTHLY_GROSS,
            pay_period=PayPeriod.MONTHLY,
            tax_year=2025,
            net_amount=breakdown.net_annual,
            total_deductions=breakdown.total_deductions,
            breakdown=breakdown.to_dict(),
            is_active=True,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    items = {i["key"]: Decimal(i["amount_period"]) for i in profile.breakdown["items"]}

    # --- Four months of activity. Each month: a payslip posted as a multi-line
    # entry, everyday spending, and a savings transfer.
    #
    # (day, kind, counter_code, money_code, amount, memo, payee)
    MONTHLY_PATTERN = [
        (2, "expense", "5010", "1020", "9500.00", "Rent", "Ayala Land Leasing"),
        (3, "expense", "5020", "1020", "2400.00", "Electricity + water", "Meralco"),
        (5, "expense", "5030", "1040", "3200.00", "Weekly groceries", "SM Supermarket"),
        (6, "expense", "5050", "1040", "1450.00", "Grab + jeepney", "Grab"),
        (8, "expense", "5120", "2010", "899.00", "Mobile + streaming", "Globe Telecom"),
        (11, "expense", "5040", "1010", "1180.00", "Dining out", "Jollibee"),
        (14, "expense", "5030", "1040", "2850.00", "Groceries", "SM Supermarket"),
        (16, "expense", "5090", "1020", "3000.00", "Family support", None),
        (18, "expense", "5060", "1010", "760.00", "Maintenance meds", "Mercury Drug"),
        (21, "expense", "5100", "1040", "620.00", "Cinema", None),
        (24, "expense", "5050", "1040", "1320.00", "Commute", "Grab"),
        (26, "expense", "5030", "1040", "2600.00", "Groceries", "SM Supermarket"),
    ]

    for months_back in (3, 2, 1, 0):
        month = _month_start(this_month, months_back)

        # Payslip: gross credited to income, each deduction debited, net banked.
        payslip_lines = []
        deductions = Decimal("0")
        for key, code in (
            ("sss", "6020"),
            ("philhealth", "6030"),
            ("pagibig", "6040"),
            ("income_tax", "6010"),
        ):
            amount = items.get(key, Decimal("0"))
            if amount > 0:
                payslip_lines.append(
                    LineInput(account_id=chart[code].id, debit=amount, memo=key.upper())
                )
                deductions += amount
        net = items["gross"] - deductions
        payslip_lines.append(
            LineInput(account_id=chart["1020"].id, debit=net, memo="Net take-home")
        )
        payslip_lines.append(
            LineInput(account_id=chart["4010"].id, credit=items["gross"], memo="Gross salary")
        )
        post_entry(
            db,
            user.id,
            occurred_at=datetime.combine(month, time(9, 0)),
            lines=payslip_lines,
            memo="Day job · payslip",
            source=EntrySource.PAYSLIP,
            source_ref=f"seed-{month:%Y%m}",
        )

        # Freelance income, every other month.
        if months_back % 2 == 0:
            post_entry(
                db,
                user.id,
                occurred_at=datetime.combine(month + timedelta(days=12), time(17, 45)),
                lines=[
                    LineInput(account_id=chart["1020"].id, debit=Decimal("6500.00")),
                    LineInput(account_id=chart["4050"].id, credit=Decimal("6500.00")),
                ],
                memo="Side project milestone",
            )

        # Top up the wallet and the cash tin for the month, from payroll.
        #
        # Derived from the spending pattern rather than hard-coded: a person
        # funds the accounts they are about to spend from, and deriving it
        # means the demo can never show the impossible — an asset account
        # spent into a negative balance.
        funding: dict[str, Decimal] = {}
        for day, _kind, _counter, money_code, amount, _memo, _payee in MONTHLY_PATTERN:
            if month + timedelta(days=day - 1) > today:
                continue
            if money_code in ("1040", "1010"):
                funding[money_code] = funding.get(money_code, Decimal("0")) + Decimal(amount)
        for money_code, needed in sorted(funding.items()):
            post_entry(
                db,
                user.id,
                occurred_at=datetime.combine(month, time(9, 30)),
                lines=[
                    LineInput(account_id=chart[money_code].id, debit=needed),
                    LineInput(account_id=chart["1020"].id, credit=needed),
                ],
                memo=f"Top up {chart[money_code].name.lower()}",
                source=EntrySource.TRANSFER,
            )

        for day, _kind, counter_code, money_code, amount, memo, payee_name in MONTHLY_PATTERN:
            when = month + timedelta(days=day - 1)
            if when > today:
                continue
            payee = payees.get(payee_name) if payee_name else None
            post_entry(
                db,
                user.id,
                occurred_at=datetime.combine(when, time(12, 30)),
                lines=[
                    LineInput(account_id=chart[counter_code].id, debit=Decimal(amount)),
                    LineInput(account_id=chart[money_code].id, credit=Decimal(amount)),
                ],
                memo=memo,
                payee_id=payee.id if payee else None,
            )

        # Pay the card off. Debiting the liability reduces what is owed; the
        # spending itself was already recorded when each charge was made.
        card_charges = sum(
            (
                Decimal(amount)
                for day, _k, _c, money_code, amount, _m, _p in MONTHLY_PATTERN
                if money_code == "2010" and month + timedelta(days=day - 1) <= today
            ),
            Decimal("0"),
        )
        card_day = month + timedelta(days=25)
        if card_charges > 0 and card_day <= today:
            post_entry(
                db,
                user.id,
                occurred_at=datetime.combine(card_day, time(10, 0)),
                lines=[
                    LineInput(account_id=chart["2010"].id, debit=card_charges),
                    LineInput(account_id=chart["1020"].id, credit=card_charges),
                ],
                memo="Credit card payment",
                source=EntrySource.TRANSFER,
            )

        # Money set aside. A transfer between two asset accounts — it moves the
        # balance without ever registering as spending.
        transfer_day = month + timedelta(days=27)
        if transfer_day <= today:
            post_entry(
                db,
                user.id,
                occurred_at=datetime.combine(transfer_day, time(20, 0)),
                lines=[
                    LineInput(account_id=chart["1030"].id, debit=Decimal("5000.00")),
                    LineInput(account_id=chart["1020"].id, credit=Decimal("5000.00")),
                ],
                memo="Monthly savings",
                source=EntrySource.TRANSFER,
            )

    # --- Budgets for the current and two prior months, so the 3M/YTD/All
    # scopes have real data on first run.
    for code, limit in (("5030", "9000"), ("5040", "2000"), ("5050", "3000")):
        for months_back in (0, 1, 2):
            month = _month_start(this_month, months_back)
            db.add(
                Budget(
                    user_id=user.id,
                    account_id=chart[code].id,
                    year=month.year,
                    month=month.month,
                    limit_amount=Decimal(limit),
                )
            )
    db.commit()


def main() -> int:
    db = SessionLocal()
    try:
        seed_demo(db)

        from app.models.journal import JournalLine

        print("Ledger seeded:")
        print(f"  accounts          {db.query(Account).count():>6}")
        print(f"  payees            {db.query(Payee).count():>6}")
        print(f"  journal_entries   {db.query(JournalEntry).count():>6}")
        print(f"  journal_lines     {db.query(JournalLine).count():>6}")
        print(f"  budgets           {db.query(Budget).count():>6}")
        print(f"  salary_profiles   {db.query(SalaryProfile).count():>6}")
        # stdout is block-buffered when piped; without this the stderr branch
        # below overtakes the summary above and the failure reads as if the
        # ledger seed never ran.
        sys.stdout.flush()

        # The warehouse is derived data, so a failure here leaves the ledger
        # perfectly usable — say so plainly rather than dumping a traceback
        # over a seed that actually succeeded.
        from app.warehouse import etl
        from app.warehouse.engine import LOCKED_HINT, WarehouseError, is_locked

        try:
            counts = etl.rebuild_all(db)
        except WarehouseError as exc:
            print(f"\nLedger seeded, but the warehouse load failed: {exc}", file=sys.stderr)
            if is_locked(exc):
                print(LOCKED_HINT, file=sys.stderr)
            else:
                print(
                    "\nRe-run the load on its own once the cause is cleared:\n"
                    "\n    uv run python -m app.warehouse.rebuild\n",
                    file=sys.stderr,
                )
            return 1

        print("Warehouse loaded:")
        for table, count in counts.items():
            print(f"  {table:<18}{count:>6}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
