"""Structured output of a salary/tax computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    """Coerce to 2dp Decimal (half-up)."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass
class LineItem:
    key: str
    label: str
    amount: Decimal
    # gross | tax | social | net | info (info = shown but not deducted, e.g. AU super)
    kind: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "amount": str(money(self.amount)),
            "kind": self.kind,
        }


@dataclass
class Breakdown:
    region: str
    currency: str
    tax_year: int
    pay_period: str
    gross_annual: Decimal
    net_annual: Decimal
    total_tax: Decimal
    total_social: Decimal
    total_deductions: Decimal
    items: list[LineItem] = field(default_factory=list)

    @property
    def effective_rate(self) -> Decimal:
        if self.gross_annual == 0:
            return Decimal("0")
        return (self.total_deductions / self.gross_annual).quantize(Decimal("0.0001"))

    def periodic(self, amount: Decimal) -> Decimal:
        """Scale an annual amount to the profile's pay period."""
        factor = Decimal("12") if self.pay_period == "monthly" else Decimal("1")
        return money(amount / factor)

    def to_dict(self) -> dict:
        return {
            "region": self.region,
            "currency": self.currency,
            "tax_year": self.tax_year,
            "pay_period": self.pay_period,
            "gross_annual": str(money(self.gross_annual)),
            "net_annual": str(money(self.net_annual)),
            "gross_period": str(self.periodic(self.gross_annual)),
            "net_period": str(self.periodic(self.net_annual)),
            "total_tax": str(money(self.total_tax)),
            "total_social": str(money(self.total_social)),
            "total_deductions": str(money(self.total_deductions)),
            "effective_rate": str(self.effective_rate),
            "items": [i.to_dict() for i in self.items],
        }
