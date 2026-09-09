"""Pure-function tests for the PH tax engine (no DB)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax import engine
from app.tax.brackets import D, progressive_tax
from app.tax.regions import ph


def annual(gross: str):
    return engine.compute(Decimal(gross), pay_period="annual", year=2025)


def test_ph_rule_is_registered():
    rule = engine.get_rule()
    assert rule.key == "PH"
    assert rule.modelled_as == "Philippines (national)"


def test_unknown_regime_raises():
    with pytest.raises(ValueError, match="No tax rule registered"):
        engine.get_rule("XX")


def test_progressive_tax_zero_and_bounds():
    brackets = [(D(0), D("0")), (D(1000), D("0.10")), (D(2000), D("0.20"))]
    assert progressive_tax(D(0), brackets) == 0
    assert progressive_tax(D(-50), brackets) == 0
    assert progressive_tax(D(1500), brackets) == Decimal("50")  # 500 * 0.10
    assert progressive_tax(D(3000), brackets) == Decimal("300")  # 100 + 200


def test_breakdown_always_reconciles():
    """Gross minus every deduction must equal net, at any income."""
    for gross in ("120000", "250000", "400000", "900000", "2500000"):
        b = annual(gross)
        assert b.gross_annual - b.total_deductions == b.net_annual, gross
        assert b.total_tax + b.total_social == b.total_deductions, gross


def test_line_items_cover_the_ph_statutory_set():
    keys = {item.key for item in annual("400000").items}
    assert keys == {"gross", "sss", "philhealth", "pagibig", "income_tax", "net"}


def test_below_the_train_threshold_no_income_tax():
    """Contributions are deductible, so 250k gross falls under the 250k
    zero-rate ceiling once they are removed."""
    b = annual("250000")
    assert b.total_tax == 0
    assert b.total_social > 0


def test_contributions_are_deducted_before_tax():
    b = annual("500000")
    taxable = b.gross_annual - b.total_social
    expected = ph.progressive_tax(taxable, ph.BRACKETS)
    assert b.total_tax == pytest.approx(float(expected), abs=1.0)


def test_effective_rate_is_regressive_below_the_contribution_floors():
    """A documented, *correct* property of the PH regime: the SSS and
    PhilHealth floors are flat pesos, so at very low incomes they consume a
    larger share of gross than they do just above the floor."""
    low = annual("60000")
    higher = annual("200000")
    assert low.effective_rate > higher.effective_rate


def test_contributions_are_capped():
    """Above the ceilings, contributions stop growing with income."""
    mid = annual("1200000")
    high = annual("5000000")
    assert mid.total_social == high.total_social


def test_monthly_annualizes_then_scales_back():
    monthly = engine.compute(Decimal("32000"), pay_period="monthly", year=2025)
    yearly = annual("384000")
    assert monthly.gross_annual == yearly.gross_annual
    assert monthly.net_annual == yearly.net_annual
    assert monthly.periodic(monthly.gross_annual) == Decimal("32000.00")


def test_to_dict_carries_both_period_and_annual_amounts():
    payload = engine.compute(Decimal("32000"), pay_period="monthly", year=2025).to_dict()
    gross = next(i for i in payload["items"] if i["key"] == "gross")
    assert gross["amount"] == "384000.00"
    assert gross["amount_period"] == "32000.00"
    assert payload["gross_period"] == "32000.00"


def test_zero_gross_has_a_zero_effective_rate():
    b = engine.compute(Decimal("0.01"), pay_period="annual", year=2025)
    assert b.effective_rate >= 0
