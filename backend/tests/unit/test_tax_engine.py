"""Pure-function tests for the region tax engine (no DB)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.base import Region
from app.tax import engine
from app.tax.brackets import D, progressive_tax


def annual(region: Region, gross: str):
    return engine.compute(Decimal(gross), region, pay_period="annual", year=2025)


def test_all_regions_registered():
    assert set(engine.supported_regions()) == {Region.PH, Region.US, Region.AU, Region.EU}


def test_progressive_tax_zero_and_bounds():
    brackets = [(D(0), D("0")), (D(1000), D("0.10")), (D(2000), D("0.20"))]
    assert progressive_tax(D(0), brackets) == 0
    assert progressive_tax(D(-50), brackets) == 0
    assert progressive_tax(D(1500), brackets) == Decimal("50")  # 500 * 0.10
    assert progressive_tax(D(3000), brackets) == Decimal("300")  # 100 + 200


def test_us_federal_60k_single():
    b = annual(Region.US, "60000")
    assert b.total_tax == Decimal("5161.50")
    assert b.total_social == Decimal("4590.00")  # SS 3720 + Medicare 870
    assert b.net_annual == Decimal("50248.50")


def test_ph_60k_below_tax_threshold():
    b = annual(Region.PH, "60000")
    # SSS 2700 + PhilHealth 3000 (floor) + Pag-IBIG 1200
    assert b.total_social == Decimal("6900.00")
    assert b.total_tax == Decimal("0.00")  # taxable 53100 < 250k
    assert b.net_annual == Decimal("53100.00")


def test_au_60k_super_is_informational():
    b = annual(Region.AU, "60000")
    assert b.total_tax == Decimal("8788.00")
    assert b.total_social == Decimal("1200.00")  # Medicare levy 2%
    assert b.net_annual == Decimal("50012.00")
    # Superannuation appears but is NOT part of deductions/net.
    super_item = next(i for i in b.items if i.key == "super")
    assert super_item.kind == "info"
    assert b.net_annual == b.gross_annual - b.total_deductions


def test_eu_germany_60k():
    b = annual(Region.EU, "60000")
    assert b.total_social == Decimal("12270.00")
    assert b.total_tax == Decimal("14680.71")
    assert b.net_annual == Decimal("33049.29")


@pytest.mark.parametrize("region", [Region.PH, Region.US, Region.AU, Region.EU])
def test_net_plus_deductions_equals_gross(region):
    b = annual(region, "90000")
    assert b.net_annual + b.total_deductions == b.gross_annual


@pytest.mark.parametrize("region", [Region.PH, Region.US, Region.AU, Region.EU])
def test_effective_rate_increases_with_income(region):
    # Compare incomes above statutory contribution floors: below the floor,
    # minimum-contribution rules (e.g. PH SSS/PhilHealth) make the effective
    # rate regressive, so monotonicity only holds in the progressive range.
    low = annual(region, "200000").effective_rate
    high = annual(region, "2000000").effective_rate
    assert high >= low  # progressive systems


def test_monthly_annualization():
    monthly = engine.compute(Decimal("5000"), Region.US, pay_period="monthly", year=2025)
    yearly = engine.compute(Decimal("60000"), Region.US, pay_period="annual", year=2025)
    assert monthly.net_annual == yearly.net_annual
    assert monthly.pay_period == "monthly"
