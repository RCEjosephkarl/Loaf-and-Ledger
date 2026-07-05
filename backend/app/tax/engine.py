"""Region tax engine — strategy interface + registry (F1).

Each region implements :class:`TaxRule`; the numbers live in module-level config
inside each region file. Add a region by registering a new rule; add a tax year by
extending its config — no change to callers.

DISCLAIMER: figures are planning-grade approximations of national statutory rules,
not tax-filing advice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.models.base import Region
from app.tax.models import Breakdown, money


class TaxRule(ABC):
    region: Region
    currency: str
    modelled_as: str  # human label for the national regime used (e.g. "Germany")

    @abstractmethod
    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        """Compute a full breakdown from annual gross for the given tax year."""


_REGISTRY: dict[Region, TaxRule] = {}


def register(rule: TaxRule) -> TaxRule:
    _REGISTRY[rule.region] = rule
    return rule


def supported_regions() -> list[Region]:
    return sorted(_REGISTRY.keys(), key=lambda r: r.value)


def get_rule(region: Region) -> TaxRule:
    if region not in _REGISTRY:
        raise ValueError(f"No tax rule registered for region {region!r}")
    return _REGISTRY[region]


def compute(
    gross: Decimal,
    region: Region,
    *,
    pay_period: str = "monthly",
    year: int | None = None,
) -> Breakdown:
    """Compute a breakdown from a gross amount expressed in `pay_period` terms."""
    rule = get_rule(region)
    factor = Decimal("12") if pay_period == "monthly" else Decimal("1")
    gross_annual = money(Decimal(str(gross)) * factor)
    year = year or DEFAULT_YEAR
    breakdown = rule.compute_annual(gross_annual, year)
    breakdown.pay_period = pay_period
    return breakdown


DEFAULT_YEAR = 2025


def load_rules() -> None:
    """Import region modules so their register() calls run."""
    from app.tax.regions import au, de, ph, us  # noqa: F401


load_rules()
