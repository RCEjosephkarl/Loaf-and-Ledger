"""Deterministic, transparent insights (F3).

Rule-based on purpose: a number is more useful when the app can say *why* it
matters, and money advice from an opaque model is worse than none. Every rule
below is a plain comparison the user could redo by hand.

The rules read warehouse figures, so they see the same numbers the charts do —
including the transfer split, which lets them talk about saving without
mistaking it for spending.
"""

from __future__ import annotations

from decimal import Decimal

from app.tax.models import money

ZERO = Decimal("0")
SAVINGS_TARGET = Decimal("0.20")


#: The peso sign, so the API's prose matches the UI's figures.
SYMBOL = "\u20b1"


def _fmt(amount: Decimal) -> str:
    return f"{SYMBOL}{money(amount):,}"


def savings_rate(income: Decimal | None, expense: Decimal) -> Decimal:
    """The share of what came in over a window that is still yours.

    Both figures are read over the *same* window. An earlier version used the
    active payslip's net-per-period as the reference, which silently compared
    one month of salary against however long the selected range happened to be
    — over "All" that produced savings rates in the hundreds of percent.
    Window income is the only reference that is dimensionally comparable to
    window expense.
    """
    if not income or income <= 0:
        return ZERO
    return ((income - expense) / income).quantize(Decimal("0.0001"))


def generate(
    *,
    totals: dict,
    accounts: list[dict],
    salary_net_period: Decimal | None = None,
    transfer_volume: Decimal = ZERO,
) -> list[dict]:
    insights: list[dict] = []
    income = totals["total_income"]
    expense = totals["total_expense"]

    if income > 0:
        rate = savings_rate(income, expense)
        if rate < 0:
            insights.append(
                {
                    "key": "overspend",
                    "severity": "warning",
                    "title": "Spending exceeds income",
                    "detail": f"Expenses ({_fmt(expense)}) are above everything that came "
                    f"in ({_fmt(income)}) for this period.",
                }
            )
        elif rate < SAVINGS_TARGET:
            insights.append(
                {
                    "key": "low_savings",
                    "severity": "warning",
                    "title": "Savings rate below 20%",
                    "detail": f"Keeping {rate * 100:.0f}% of what came in. "
                    "A common target is 20%+.",
                }
            )
        else:
            insights.append(
                {
                    "key": "healthy_savings",
                    "severity": "good",
                    "title": "Healthy savings rate",
                    "detail": f"Keeping {rate * 100:.0f}% of everything that came in this period.",
                }
            )

    expenses = [a for a in accounts if a["flow_class"] == "outflow"]
    discretionary = [a for a in expenses if not a["is_statutory"]]
    statutory = [a for a in expenses if a["is_statutory"]]

    if expenses and expense > 0:
        top = max(expenses, key=lambda a: a["total"])
        share = (top["total"] / expense).quantize(Decimal("0.01"))
        if share >= Decimal("0.40"):
            insights.append(
                {
                    "key": "concentrated_spend",
                    "severity": "info",
                    "title": f"{top['account_name']} dominates spending",
                    "detail": f"{share * 100:.0f}% of outgoings went to {top['account_name']} "
                    f"({_fmt(top['total'])}).",
                }
            )
        elif share < Decimal("0.25"):
            insights.append(
                {
                    "key": "diversified_spend",
                    "severity": "good",
                    "title": "Spending is well spread out",
                    "detail": "No single account ate more than a quarter of your outgoings — "
                    "a balanced loaf, not a lopsided one.",
                }
            )

    statutory_total = money(sum((a["total"] for a in statutory), ZERO))
    if statutory_total > 0 and income > 0:
        share = (statutory_total / income).quantize(Decimal("0.01"))
        insights.append(
            {
                "key": "statutory_share",
                "severity": "info",
                "title": "Where the mandatory slice went",
                "detail": f"{_fmt(statutory_total)} — {share * 100:.0f}% of what came in — went "
                "to BIR, SSS, PhilHealth and Pag-IBIG before you could spend it.",
            }
        )

    # Only double entry makes this rule possible: transfers are a distinct
    # movement, so putting money aside can be praised rather than counted
    # against you as spending.
    if transfer_volume > 0:
        insights.append(
            {
                "key": "money_set_aside",
                "severity": "good",
                "title": "Money moved, not spent",
                "detail": f"{_fmt(transfer_volume)} moved between your own accounts this "
                "period — transfers, not outgoings, and excluded from every expense figure.",
            }
        )

    income_streams = [a for a in accounts if a["flow_class"] == "inflow" and a["total"] > 0]
    if len(income_streams) > 1:
        insights.append(
            {
                "key": "multiple_income_streams",
                "severity": "info",
                "title": "Multiple slices of income",
                "detail": f"You're not living off one loaf — {len(income_streams)} income "
                "sources contributed this period.",
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

    if not discretionary and not insights:
        insights.append(
            {
                "key": "no_signal",
                "severity": "info",
                "title": "Not enough data yet",
                "detail": "Add a salary profile and a few entries to unlock personalized insights.",
            }
        )
    return insights
