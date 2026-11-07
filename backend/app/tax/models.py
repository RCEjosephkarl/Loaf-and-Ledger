"""Structured output of a salary/tax computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
PERIOD_FACTORS = {"annual": Decimal("1"), "monthly": Decimal("12"), "fortnightly": Decimal("26")}


def period_factor(pay_period: str) -> Decimal:
    try:
        return PERIOD_FACTORS[pay_period]
    except KeyError as exc:
        raise ValueError(f"Unknown pay period: {pay_period}") from exc


def money(value: Decimal | int | float | str) -> Decimal:
    """Coerce to 2dp Decimal (half-up)."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass
class LineItem:
    key: str
    label: str
    amount: Decimal
    # gross | tax | social | net | info (info = shown but not deducted)
    kind: str

    def to_dict(self, period_factor: Decimal = Decimal("1")) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "amount": str(money(self.amount)),
            # The same figure expressed in the profile's pay period. Carried in
            # the snapshot so the ledger posting and the warehouse's
            # fact_payslip_item never have to re-derive it.
            "amount_period": str(money(Decimal(str(self.amount)) / period_factor)),
            "kind": self.kind,
        }


@dataclass
class Breakdown:
    """A gross-to-net computation. Single-currency (PHP) — see models.base."""

    tax_year: int
    pay_period: str
    gross_annual: Decimal
    net_annual: Decimal
    total_tax: Decimal
    total_social: Decimal
    total_deductions: Decimal
    items: list[LineItem] = field(default_factory=list)

    @property
    def period_factor(self) -> Decimal:
        return period_factor(self.pay_period)

    @property
    def effective_rate(self) -> Decimal:
        if self.gross_annual == 0:
            return Decimal("0")
        return (self.total_deductions / self.gross_annual).quantize(Decimal("0.0001"))

    def periodic(self, amount: Decimal) -> Decimal:
        """Scale an annual amount to the profile's pay period."""
        return money(Decimal(str(amount)) / self.period_factor)

    def to_dict(self) -> dict:
        factor = self.period_factor
        items = [i.to_dict(factor) for i in self.items]
        gross_period = self.periodic(self.gross_annual)
        deductions = sum(
            (Decimal(i["amount_period"]) for i in items if i["kind"] in ("tax", "social")),
            Decimal("0"),
        )
        net_period = money(gross_period - deductions)
        for item in items:
            if item["kind"] == "net":
                item["amount_period"] = str(net_period)
        return {
            "tax_year": self.tax_year,
            "pay_period": self.pay_period,
            "gross_annual": str(money(self.gross_annual)),
            "net_annual": str(money(self.net_annual)),
            "gross_period": str(gross_period),
            "net_period": str(net_period),
            "total_tax": str(money(self.total_tax)),
            "total_social": str(money(self.total_social)),
            "total_deductions": str(money(self.total_deductions)),
            "effective_rate": str(self.effective_rate),
            "items": items,
        }
