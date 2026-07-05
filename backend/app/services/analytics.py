"""Aggregations + rule-based insights derived from salary (F1) and ledger (F2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Region, TxDirection
from app.models.category import Category
from app.models.salary import SalaryProfile
from app.models.transaction import Transaction
from app.services.currency import convert
from app.tax.models import money

ZERO = Decimal("0")


def active_salary(db: Session, user_id: int) -> SalaryProfile | None:
    return (
        db.execute(
            select(SalaryProfile)
            .where(SalaryProfile.user_id == user_id, SalaryProfile.is_active.is_(True))
            .order_by(SalaryProfile.updated_at.desc())
        )
        .scalars()
        .first()
    )


def _query_transactions(
    db: Session,
    user_id: int,
    start: date | None,
    end: date | None,
    region: Region | None,
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Transaction.occurred_on >= start)
    if end is not None:
        stmt = stmt.where(Transaction.occurred_on <= end)
    if region is not None:
        stmt = stmt.where(Transaction.region == region)
    return list(db.execute(stmt).scalars().all())


def category_map(db: Session) -> dict[int, Category]:
    return {c.id: c for c in db.execute(select(Category)).scalars().all()}


def aggregate(
    db: Session,
    user_id: int,
    *,
    currency: str,
    start: date | None = None,
    end: date | None = None,
    region: Region | None = None,
) -> dict:
    """Totals + per-category breakdown, all converted to `currency`."""
    txns = _query_transactions(db, user_id, start, end, region)
    cats = category_map(db)

    total_income = ZERO
    total_expense = ZERO
    per_category: dict[int, dict] = {}

    for tx in txns:
        amt = convert(db, Decimal(str(tx.amount)), tx.currency, currency)
        if tx.direction == TxDirection.INBOUND:
            total_income += amt
        else:
            total_expense += amt
        bucket = per_category.setdefault(
            tx.category_id,
            {
                "category_id": tx.category_id,
                "category_name": cats.get(tx.category_id).name
                if tx.category_id in cats
                else "Uncategorized",
                "direction": tx.direction,
                "total": ZERO,
            },
        )
        bucket["total"] += amt

    for b in per_category.values():
        b["total"] = money(b["total"])

    return {
        "total_income": money(total_income),
        "total_expense": money(total_expense),
        "net_cashflow": money(total_income - total_expense),
        "per_category": list(per_category.values()),
    }


def top_expense_categories(agg: dict, limit: int = 5) -> list[dict]:
    expenses = [c for c in agg["per_category"] if c["direction"] == TxDirection.OUTBOUND]
    return sorted(expenses, key=lambda c: c["total"], reverse=True)[:limit]


def generate_insights(
    db: Session,
    user_id: int,
    *,
    currency: str,
    agg: dict,
    salary_net_period: Decimal | None,
) -> list[dict]:
    """Deterministic, transparent insights — no ML (F3)."""
    insights: list[dict] = []
    income = agg["total_income"]
    expense = agg["total_expense"]

    # Reference monthly income: prefer salary net, else ledger income.
    reference = salary_net_period if salary_net_period and salary_net_period > 0 else income

    if reference and reference > 0:
        savings = reference - expense
        rate = (savings / reference).quantize(Decimal("0.01"))
        if rate < 0:
            insights.append(
                {
                    "key": "overspend",
                    "severity": "warning",
                    "title": "Spending exceeds income",
                    "detail": f"Expenses ({money(expense)} {currency}) are above your reference "
                    f"income ({money(reference)} {currency}) for this period.",
                }
            )
        elif rate < Decimal("0.20"):
            insights.append(
                {
                    "key": "low_savings",
                    "severity": "warning",
                    "title": "Savings rate below 20%",
                    "detail": f"Saving {rate * 100:.0f}% of income. A common target is 20%+.",
                }
            )
        else:
            insights.append(
                {
                    "key": "healthy_savings",
                    "severity": "good",
                    "title": "Healthy savings rate",
                    "detail": f"Saving {rate * 100:.0f}% of your reference income this period.",
                }
            )

    tops = top_expense_categories(agg, limit=1)
    if tops and expense > 0:
        top = tops[0]
        share = (top["total"] / expense).quantize(Decimal("0.01"))
        if share >= Decimal("0.40"):
            insights.append(
                {
                    "key": "concentrated_spend",
                    "severity": "info",
                    "title": f"{top['category_name']} dominates spending",
                    "detail": f"{share * 100:.0f}% of expenses went to {top['category_name']} "
                    f"({top['total']} {currency}).",
                }
            )

    if not insights:
        insights.append(
            {
                "key": "no_signal",
                "severity": "info",
                "title": "Not enough data yet",
                "detail": "Add salary and a few transactions to unlock personalized insights.",
            }
        )
    return insights


def savings_rate(reference: Decimal | None, expense: Decimal) -> Decimal:
    if not reference or reference <= 0:
        return ZERO
    return ((reference - expense) / reference).quantize(Decimal("0.0001"))
