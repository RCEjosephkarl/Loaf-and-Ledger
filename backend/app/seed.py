"""Idempotent seed: single user, reference data, and a demo dataset.

Run with:  uv run python -m app.seed
Safe to run repeatedly — existing rows are left untouched.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.base import REGION_CURRENCY, Region, TxDirection
from app.models.budget import Budget
from app.models.category import Category
from app.models.fx import ExchangeRate
from app.models.jurisdiction import Jurisdiction
from app.models.salary import PayPeriod, SalaryProfile
from app.models.transaction import Transaction
from app.services.user import get_single_user
from app.tax import engine

JURISDICTIONS = [
    (Region.PH, "Philippines", "Philippines (national)"),
    (Region.US, "United States", "United States (federal)"),
    (Region.AU, "Australia", "Australia (national)"),
    (Region.EU, "European Union", "Germany (EU representative)"),
]

# 1 USD = <rate> quote (approximate mid-2025 levels; refresh manually).
FX_USD = {"PHP": Decimal("58.00"), "AUD": Decimal("1.52"), "EUR": Decimal("0.92")}

INBOUND = [
    "Base salary",
    "Overtime",
    "Bonus",
    "Commission",
    "Allowances",
    "Reimbursements",
    "Dividends",
    "Interest",
    "Freelance income",
    "Other income",
]
OUTBOUND = [
    "Housing",
    "Utilities",
    "Groceries",
    "Dining",
    "Transport",
    "Healthcare",
    "Insurance",
    "Education",
    "Debt repayment",
    "Savings & investment",
    "Entertainment",
    "Shopping",
    "Subscriptions",
    "Travel",
    "Family & dependents",
    "Charity",
    "Miscellaneous",
]
STATUTORY = {
    Region.PH: ["Income tax", "SSS", "PhilHealth", "Pag-IBIG"],
    Region.US: ["Federal income tax", "Social Security", "Medicare"],
    Region.AU: ["Income tax", "Medicare levy"],
    Region.EU: [
        "Income tax",
        "Pension insurance",
        "Health insurance",
        "Unemployment insurance",
        "Long-term care insurance",
    ],
}


def _get_or_create_category(
    db: Session, name: str, direction: TxDirection, *, statutory=False, region=None
) -> Category:
    existing = db.execute(
        select(Category).where(Category.name == name, Category.direction == direction)
    ).scalar_one_or_none()
    if existing:
        return existing
    cat = Category(
        name=name, direction=direction, statutory=statutory, region=region, is_system=True
    )
    db.add(cat)
    db.flush()
    return cat


def seed_reference(db: Session) -> None:
    for region, name, modelled in JURISDICTIONS:
        if not db.execute(
            select(Jurisdiction).where(Jurisdiction.region == region)
        ).scalar_one_or_none():
            db.add(
                Jurisdiction(
                    region=region,
                    name=name,
                    currency=REGION_CURRENCY[region],
                    modelled_as=modelled,
                    supported=True,
                )
            )

    today = date.today()
    for quote, rate in FX_USD.items():
        if not db.execute(
            select(ExchangeRate).where(
                ExchangeRate.base_currency == "USD", ExchangeRate.quote_currency == quote
            )
        ).scalar_one_or_none():
            db.add(ExchangeRate(base_currency="USD", quote_currency=quote, rate=rate, as_of=today))

    for name in INBOUND:
        _get_or_create_category(db, name, TxDirection.INBOUND)
    for name in OUTBOUND:
        _get_or_create_category(db, name, TxDirection.OUTBOUND)
    for region, names in STATUTORY.items():
        for name in names:
            _get_or_create_category(
                db, f"{name} ({region.value})", TxDirection.OUTBOUND, statutory=True, region=region
            )
    db.commit()


def seed_demo(db: Session) -> None:
    user = get_single_user(db)
    user.base_currency = "USD"
    user.default_region = Region.US

    # Demo salary profile (active) — only if the user has none.
    if (
        not db.execute(select(SalaryProfile).where(SalaryProfile.user_id == user.id))
        .scalars()
        .first()
    ):
        gross = Decimal("6000")
        breakdown = engine.compute(gross, Region.US, pay_period="monthly", year=2025)
        db.add(
            SalaryProfile(
                user_id=user.id,
                label="Day job",
                region=Region.US,
                currency="USD",
                gross_amount=gross,
                pay_period=PayPeriod.MONTHLY,
                tax_year=2025,
                net_amount=breakdown.net_annual,
                total_deductions=breakdown.total_deductions,
                breakdown=breakdown.to_dict(),
                is_active=True,
            )
        )

    # Demo transactions — only if none exist.
    if not db.execute(select(Transaction).where(Transaction.user_id == user.id)).scalars().first():

        def cat(name: str, direction: TxDirection) -> int:
            return db.execute(
                select(Category.id).where(Category.name == name, Category.direction == direction)
            ).scalar_one()

        today = date.today()
        month_start = today.replace(day=1)

        # A prior month of activity so carry-over "initial fund" and the 3M/YTD/All
        # budget scopes have real history to show on first run, not just zeros.
        def _prior_month_start(base: date, months_back: int) -> date:
            idx = base.year * 12 + (base.month - 1) - months_back
            return date(idx // 12, idx % 12 + 1, 1)

        prior_month_start = _prior_month_start(month_start, 1)
        prior_demo = [
            (TxDirection.INBOUND, "Base salary", "4590.00", prior_month_start, time(9, 0), "Monthly net salary"),
            (TxDirection.OUTBOUND, "Housing", "1500.00", prior_month_start + timedelta(days=1), time(8, 5), "Rent"),
            (TxDirection.OUTBOUND, "Groceries", "410.00", prior_month_start + timedelta(days=4), time(11, 5), "Supermarket"),
            (TxDirection.OUTBOUND, "Dining", "150.00", prior_month_start + timedelta(days=9), time(19, 0), "Restaurants"),
        ]
        for direction, name, amount, when, when_time, desc in prior_demo:
            db.add(
                Transaction(
                    user_id=user.id,
                    direction=direction,
                    category_id=cat(name, direction),
                    amount=Decimal(amount),
                    currency="USD",
                    region=Region.US,
                    occurred_on=when,
                    occurred_time=when_time,
                    description=desc,
                )
            )

        demo = [
            (
                TxDirection.INBOUND,
                "Base salary",
                "4590.00",
                month_start,
                time(9, 0),
                "Monthly net salary",
            ),
            (
                TxDirection.INBOUND,
                "Freelance income",
                "600.00",
                month_start + timedelta(days=5),
                time(17, 45),
                "Side project",
            ),
            (
                TxDirection.OUTBOUND,
                "Housing",
                "1500.00",
                month_start + timedelta(days=1),
                time(8, 5),
                "Rent",
            ),
            (
                TxDirection.OUTBOUND,
                "Groceries",
                "480.00",
                month_start + timedelta(days=3),
                time(11, 20),
                "Supermarket",
            ),
            (
                TxDirection.OUTBOUND,
                "Dining",
                "220.00",
                month_start + timedelta(days=6),
                time(19, 30),
                "Restaurants",
            ),
            (
                TxDirection.OUTBOUND,
                "Transport",
                "160.00",
                month_start + timedelta(days=7),
                time(7, 50),
                "Fuel + transit",
            ),
            (
                TxDirection.OUTBOUND,
                "Subscriptions",
                "55.00",
                month_start + timedelta(days=8),
                time(21, 15),
                "Streaming + apps",
            ),
            (
                TxDirection.OUTBOUND,
                "Utilities",
                "180.00",
                month_start + timedelta(days=9),
                time(14, 40),
                "Electricity + water",
            ),
        ]
        for direction, name, amount, when, when_time, desc in demo:
            db.add(
                Transaction(
                    user_id=user.id,
                    direction=direction,
                    category_id=cat(name, direction),
                    amount=Decimal(amount),
                    currency="USD",
                    region=Region.US,
                    occurred_on=when,
                    occurred_time=when_time,
                    description=desc,
                )
            )

        # Demo budgets for the current + 2 prior months, so the 3M/YTD/All
        # period scopes on the Budgets page have real data on first run.
        groceries_id = cat("Groceries", TxDirection.OUTBOUND)
        for months_back, limit in ((0, "500"), (1, "480"), (2, "480")):
            budget_month = _prior_month_start(month_start, months_back)
            if not db.execute(
                select(Budget).where(
                    Budget.user_id == user.id,
                    Budget.category_id == groceries_id,
                    Budget.year == budget_month.year,
                    Budget.month == budget_month.month,
                )
            ).scalar_one_or_none():
                db.add(
                    Budget(
                        user_id=user.id,
                        category_id=groceries_id,
                        year=budget_month.year,
                        month=budget_month.month,
                        limit_amount=Decimal(limit),
                        currency="USD",
                    )
                )

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_reference(db)
        seed_demo(db)
        counts = {
            "categories": db.query(Category).count(),
            "jurisdictions": db.query(Jurisdiction).count(),
            "exchange_rates": db.query(ExchangeRate).count(),
            "salary_profiles": db.query(SalaryProfile).count(),
            "transactions": db.query(Transaction).count(),
            "budgets": db.query(Budget).count(),
        }
        print("Seed complete:", counts)
    finally:
        db.close()


if __name__ == "__main__":
    main()
