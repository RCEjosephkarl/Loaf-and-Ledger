"""Aggregations + rule-based insights derived from salary (F1) and ledger (F2)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, time
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


def monthly_expense_by_category(
    db: Session,
    user_id: int,
    *,
    currency: str,
    months: int,
    region: Region | None,
) -> dict:
    """Trailing-N-month expense totals per category — feeds the Analytics
    stacked-by-category chart."""
    txns = [
        t
        for t in _query_transactions(db, user_id, None, None, region)
        if t.direction == TxDirection.OUTBOUND
    ]
    cats = category_map(db)
    buckets: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for tx in txns:
        key = f"{tx.occurred_on.year:04d}-{tx.occurred_on.month:02d}"
        amt = convert(db, Decimal(str(tx.amount)), tx.currency, currency)
        buckets[key][tx.category_id] += amt

    month_keys = sorted(buckets)[-months:]
    category_ids = sorted({cid for m in month_keys for cid in buckets.get(m, {})})
    series = [
        {
            "category_id": cid,
            "category_name": cats[cid].name if cid in cats else "Uncategorized",
            "values": [money(buckets.get(m, {}).get(cid, ZERO)) for m in month_keys],
        }
        for cid in category_ids
    ]
    return {"months": month_keys, "series": series}


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
        elif share < Decimal("0.25"):
            insights.append(
                {
                    "key": "diversified_spend",
                    "severity": "good",
                    "title": "Spending is well spread out",
                    "detail": "No single category ate more than a quarter of your outgoings — "
                    "a balanced loaf, not a lopsided one.",
                }
            )

    income_streams = [
        c
        for c in agg["per_category"]
        if c["direction"] == TxDirection.INBOUND and c["total"] > 0
    ]
    if len(income_streams) > 1:
        insights.append(
            {
                "key": "multiple_income_streams",
                "severity": "info",
                "title": "Multiple slices of income",
                "detail": f"You're not living off one loaf — {len(income_streams)} income "
                f"streams contributed this period.",
            }
        )

    if expense == 0 and income > 0:
        insights.append(
            {
                "key": "no_expenses_yet",
                "severity": "info",
                "title": "Nothing spent yet",
                "detail": "No debits recorded this period — the crust is still intact.",
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


def running_balance_by_transaction(
    db: Session,
    user_id: int,
    *,
    currency: str,
    region: Region | None,
) -> dict[int, str]:
    """Full-history cumulative balance per transaction, keyed by id — feeds
    the Ledger table's running-balance column. Always spans the user's whole
    history (ignores any date-range filter): a running balance that reset at
    an arbitrary window start wouldn't reflect a real account balance."""
    txns = sorted(
        _query_transactions(db, user_id, None, None, region),
        key=lambda t: (t.occurred_on, t.occurred_time or time.min, t.id),
    )
    running = ZERO
    balances: dict[int, str] = {}
    for tx in txns:
        amt = convert(db, Decimal(str(tx.amount)), tx.currency, currency)
        running += amt if tx.direction == TxDirection.INBOUND else -amt
        balances[tx.id] = money(running)
    return balances


def savings_rate(reference: Decimal | None, expense: Decimal) -> Decimal:
    if not reference or reference <= 0:
        return ZERO
    return ((reference - expense) / reference).quantize(Decimal("0.0001"))


def running_balance(
    db: Session,
    user_id: int,
    *,
    currency: str,
    start: date | None,
    end: date | None,
    region: Region | None,
) -> list[dict]:
    """Cumulative net cash flow (income - expense) day over day, oldest first."""
    txns = _query_transactions(db, user_id, start, end, region)
    daily: dict[date, dict[str, Decimal]] = defaultdict(lambda: {"income": ZERO, "expense": ZERO})
    for tx in txns:
        amt = convert(db, Decimal(str(tx.amount)), tx.currency, currency)
        side = "income" if tx.direction == TxDirection.INBOUND else "expense"
        daily[tx.occurred_on][side] += amt

    running = ZERO
    points: list[dict] = []
    for d in sorted(daily):
        income = daily[d]["income"]
        expense = daily[d]["expense"]
        net = income - expense
        running += net
        points.append(
            {
                "date": d,
                "income": money(income),
                "expense": money(expense),
                "net": money(net),
                "balance": money(running),
            }
        )
    return points
