"""EU modelled via Germany — 2024 Einkommensteuer formula + social insurance.

'EU' is not one tax regime; v1 uses Germany as the representative national system.
Other member states can be added later as their own jurisdictions.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.base import Region
from app.tax.brackets import D, capped_contribution
from app.tax.engine import TaxRule, register
from app.tax.models import Breakdown, LineItem, money

# Employee shares of statutory social insurance (2024), with annual ceilings.
PENSION_RATE, PENSION_CEIL = D("0.093"), D(90_600)
HEALTH_RATE, HEALTH_CEIL = D("0.0815"), D(62_100)  # 7.3% + ~0.85% Zusatzbeitrag
UNEMP_RATE, UNEMP_CEIL = D("0.013"), D(90_600)
CARE_RATE, CARE_CEIL = D("0.017"), D(62_100)


def income_tax_2024(zve: Decimal) -> Decimal:
    """Germany's 2024 income-tax formula (Grundtarif) on taxable income zvE."""
    x = zve
    if x <= D(11_604):
        return Decimal("0")
    if x <= D(17_005):
        y = (x - D(11_604)) / D(10_000)
        return (D("922.98") * y + D(1_400)) * y
    if x <= D(66_760):
        z = (x - D(17_005)) / D(10_000)
        return (D("181.19") * z + D(2_397)) * z + D("1025.38")
    if x <= D(277_825):
        return D("0.42") * x - D("10602.13")
    return D("0.45") * x - D("18936.88")


class GermanyRule(TaxRule):
    region = Region.EU
    currency = "EUR"
    modelled_as = "Germany (EU representative)"

    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        pension = capped_contribution(gross_annual, PENSION_RATE, annual_ceiling=PENSION_CEIL)
        health = capped_contribution(gross_annual, HEALTH_RATE, annual_ceiling=HEALTH_CEIL)
        unemployment = capped_contribution(gross_annual, UNEMP_RATE, annual_ceiling=UNEMP_CEIL)
        care = capped_contribution(gross_annual, CARE_RATE, annual_ceiling=CARE_CEIL)
        social = pension + health + unemployment + care

        # Approximation: apply the tax formula to gross as taxable income (zvE).
        income_tax = income_tax_2024(gross_annual)
        if income_tax < 0:
            income_tax = Decimal("0")

        total_deductions = social + income_tax
        net = gross_annual - total_deductions

        items = [
            LineItem("gross", "Gross salary", gross_annual, "gross"),
            LineItem("income_tax", "Income tax (Lohnsteuer)", income_tax, "tax"),
            LineItem("pension", "Pension insurance", pension, "social"),
            LineItem("health", "Health insurance", health, "social"),
            LineItem("unemployment", "Unemployment insurance", unemployment, "social"),
            LineItem("care", "Long-term care insurance", care, "social"),
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


register(GermanyRule())
