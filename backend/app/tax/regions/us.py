"""United States (federal only, single filer) — 2025 brackets + FICA."""

from __future__ import annotations

from decimal import Decimal

from app.models.base import Region
from app.tax.brackets import D, progressive_tax
from app.tax.engine import TaxRule, register
from app.tax.models import Breakdown, LineItem, money

# 2025 federal income-tax brackets, single filer (lower_bound, marginal rate).
BRACKETS = [
    (D(0), D("0.10")),
    (D(11_925), D("0.12")),
    (D(48_475), D("0.22")),
    (D(103_350), D("0.24")),
    (D(197_300), D("0.32")),
    (D(250_525), D("0.35")),
    (D(626_350), D("0.37")),
]
STANDARD_DEDUCTION = D(15_000)  # 2025 single

# FICA (employee share).
SS_RATE = D("0.062")
SS_WAGE_BASE = D(176_100)  # 2025
MEDICARE_RATE = D("0.0145")
ADDL_MEDICARE_RATE = D("0.009")
ADDL_MEDICARE_THRESHOLD = D(200_000)


class UnitedStatesRule(TaxRule):
    region = Region.US
    currency = "USD"
    modelled_as = "United States (federal)"

    def compute_annual(self, gross_annual: Decimal, year: int) -> Breakdown:
        # Federal income tax on taxable income; FICA on gross wages.
        taxable = max(gross_annual - STANDARD_DEDUCTION, Decimal("0"))
        income_tax = progressive_tax(taxable, BRACKETS)

        social_security = min(gross_annual, SS_WAGE_BASE) * SS_RATE
        medicare = gross_annual * MEDICARE_RATE
        if gross_annual > ADDL_MEDICARE_THRESHOLD:
            medicare += (gross_annual - ADDL_MEDICARE_THRESHOLD) * ADDL_MEDICARE_RATE

        social = social_security + medicare
        total_deductions = income_tax + social
        net = gross_annual - total_deductions

        items = [
            LineItem("gross", "Gross wages", gross_annual, "gross"),
            LineItem("federal_income_tax", "Federal income tax", income_tax, "tax"),
            LineItem("social_security", "Social Security", social_security, "social"),
            LineItem("medicare", "Medicare", medicare, "social"),
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


register(UnitedStatesRule())
