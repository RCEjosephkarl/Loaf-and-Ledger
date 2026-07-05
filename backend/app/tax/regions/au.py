"""Australia (resident) — 2024–25 PAYG income tax + Medicare levy + super."""

from __future__ import annotations

from decimal import Decimal

from app.models.base import Region
from app.tax.brackets import D, progressive_tax
from app.tax.engine import TaxRule, register
from app.tax.models import Breakdown, LineItem, money

# 2024-25 resident income-tax brackets (lower_bound, marginal rate).
BRACKETS = [
    (D(0), D("0")),
    (D(18_200), D("0.16")),
    (D(45_000), D("0.30")),
    (D(135_000), D("0.37")),
    (D(190_000), D("0.45")),
]
MEDICARE_LEVY_RATE = D("0.02")
MEDICARE_LEVY_THRESHOLD = D(27_222)  # below this, levy is 0 (simplified)
SUPER_RATE = D("0.115")  # employer contribution, 2024-25 (informational)


class AustraliaRule(TaxRule):
    region = Region.AU
    currency = "AUD"
    modelled_as = "Australia (national)"

    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        income_tax = progressive_tax(gross_annual, BRACKETS)
        medicare_levy = (
            gross_annual * MEDICARE_LEVY_RATE
            if gross_annual > MEDICARE_LEVY_THRESHOLD
            else Decimal("0")
        )
        # Superannuation is an employer contribution on top of salary — shown for
        # context but NOT subtracted from take-home pay.
        super_contrib = gross_annual * SUPER_RATE

        total_deductions = income_tax + medicare_levy
        net = gross_annual - total_deductions

        items = [
            LineItem("gross", "Gross salary", gross_annual, "gross"),
            LineItem("income_tax", "Income tax (PAYG)", income_tax, "tax"),
            LineItem("medicare_levy", "Medicare levy", medicare_levy, "social"),
            LineItem("net", "Net take-home", net, "net"),
            LineItem("super", "Superannuation (employer)", super_contrib, "info"),
        ]
        return Breakdown(
            region=self.region.value,
            currency=self.currency,
            tax_year=year,
            pay_period="annual",
            gross_annual=money(gross_annual),
            net_annual=money(net),
            total_tax=money(income_tax),
            total_social=money(medicare_levy),
            total_deductions=money(total_deductions),
            items=items,
        )


register(AustraliaRule())
