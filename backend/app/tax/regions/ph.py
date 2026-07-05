"""Philippines — TRAIN-law income tax + SSS / PhilHealth / Pag-IBIG (2025 est.)."""

from __future__ import annotations

from decimal import Decimal

from app.models.base import Region
from app.tax.brackets import D, capped_contribution, progressive_tax
from app.tax.engine import TaxRule, register
from app.tax.models import Breakdown, LineItem, money

# TRAIN annual income-tax brackets (lower_bound, marginal rate).
BRACKETS = [
    (D(0), D("0")),
    (D(250_000), D("0.15")),
    (D(400_000), D("0.20")),
    (D(800_000), D("0.25")),
    (D(2_000_000), D("0.30")),
    (D(8_000_000), D("0.35")),
]

# Mandatory employee contributions (annualised from monthly rules).
SSS_RATE = D("0.045")
SSS_FLOOR, SSS_CEIL = D(48_000), D(360_000)  # MSC 4,000–30,000 / month
PHILHEALTH_RATE = D("0.025")  # employee half of 5% premium
PH_FLOOR, PH_CEIL = D(120_000), D(1_200_000)  # 10,000–100,000 / month
PAGIBIG_RATE = D("0.02")
PAGIBIG_CEIL = D(60_000)  # 2% of max fund salary 5,000/month -> 100/month


class PhilippinesRule(TaxRule):
    region = Region.PH
    currency = "PHP"
    modelled_as = "Philippines (national)"

    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        sss = capped_contribution(
            gross_annual, SSS_RATE, annual_floor=SSS_FLOOR, annual_ceiling=SSS_CEIL
        )
        philhealth = capped_contribution(
            gross_annual, PHILHEALTH_RATE, annual_floor=PH_FLOOR, annual_ceiling=PH_CEIL
        )
        pagibig = capped_contribution(gross_annual, PAGIBIG_RATE, annual_ceiling=PAGIBIG_CEIL)
        social = sss + philhealth + pagibig

        # Contributions are deductible before income tax.
        taxable = max(gross_annual - social, Decimal("0"))
        income_tax = progressive_tax(taxable, BRACKETS)

        total_deductions = social + income_tax
        net = gross_annual - total_deductions

        items = [
            LineItem("gross", "Gross salary", gross_annual, "gross"),
            LineItem("sss", "SSS", sss, "social"),
            LineItem("philhealth", "PhilHealth", philhealth, "social"),
            LineItem("pagibig", "Pag-IBIG", pagibig, "social"),
            LineItem("income_tax", "Income tax", income_tax, "tax"),
            LineItem("net", "Net take-home", net, "net"),
        ]
        return Breakdown(
            region=self.region.value,
            currency=self.currency,
            tax_year=year,
            pay_period="annual",
            gross_annual=money(gross_annual),
            net_annual=money(net),
            total_tax=money(income_tax),
            total_social=money(social),
            total_deductions=money(total_deductions),
            items=items,
        )


register(PhilippinesRule())
