"""Tax engine — strategy interface + registry (F1).

v1 models the Philippines only. The registry is kept because it is the seam
that lets a second regime be added as a new module rather than an `if` in the
caller: register a rule, and `compute()` picks it up unchanged.

DISCLAIMER: figures are planning-grade approximations of national statutory
rules, not tax-filing advice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.tax.models import Breakdown, money

DEFAULT_YEAR = 2025


class TaxRule(ABC):
    key: str
    modelled_as: str  # human label for the regime (e.g. "Philippines (national)")

    @abstractmethod
    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        """Compute a full breakdown from annual gross for the given tax year."""


_REGISTRY: dict[str, TaxRule] = {}
_DEFAULT_KEY = "PH"


def register(rule: TaxRule) -> TaxRule:
    _REGISTRY[rule.key] = rule
    return rule


def get_rule(key: str = _DEFAULT_KEY) -> TaxRule:
    if key not in _REGISTRY:
        raise ValueError(f"No tax rule registered for {key!r}")
    return _REGISTRY[key]


def compute(
    gross: Decimal,
    *,
    pay_period: str = "monthly",
    year: int | None = None,
) -> Breakdown:
    """Compute a breakdown from a gross amount expressed in `pay_period` terms."""
    rule = get_rule()
    factor = Decimal("12") if pay_period == "monthly" else Decimal("1")
    gross_annual = money(Decimal(str(gross)) * factor)
    breakdown = rule.compute_annual(gross_annual, year or DEFAULT_YEAR)
    breakdown.pay_period = pay_period
    return breakdown


def load_rules() -> None:
    """Import region modules so their register() calls run."""
    from app.tax.regions import ph  # noqa: F401


load_rules()
