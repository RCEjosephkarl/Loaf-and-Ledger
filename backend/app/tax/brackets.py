"""Shared math for progressive brackets and capped contributions."""

from __future__ import annotations

from decimal import Decimal

# A bracket is (lower_bound, marginal_rate); list ascending, first lower_bound = 0.
Bracket = tuple[Decimal, Decimal]


def progressive_tax(income: Decimal, brackets: list[Bracket]) -> Decimal:
    """Marginal progressive tax on `income` given ascending (lower_bound, rate) brackets."""
    if income <= 0:
        return Decimal("0")
    tax = Decimal("0")
    for i, (lower, rate) in enumerate(brackets):
        if income <= lower:
            break
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else income
        span = min(income, upper) - lower
        if span > 0:
            tax += span * rate
    return tax


def capped_contribution(
    annual_income: Decimal,
    rate: Decimal,
    *,
    annual_floor: Decimal = Decimal("0"),
    annual_ceiling: Decimal | None = None,
) -> Decimal:
    """A percentage contribution on income clamped to [floor, ceiling]."""
    base = max(annual_income, annual_floor)
    if annual_ceiling is not None:
        base = min(base, annual_ceiling)
    return base * rate


def D(value: str | int | float) -> Decimal:  # noqa: N802 - short constructor
    return Decimal(str(value))
