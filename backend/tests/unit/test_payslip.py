"""Posting a payslip: the join between the tax engine (F1) and the ledger (F2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.models.base import EntrySource
from app.models.salary import PayPeriod, SalaryProfile
from app.services import payslip as svc
from app.services.journal import JournalError
from app.tax import engine


@pytest.fixture
def profile(db_session, user_id):
    breakdown = engine.compute(Decimal("32000"), pay_period="monthly", year=2025)
    row = SalaryProfile(
        user_id=user_id,
        label="Day job",
        gross_amount=Decimal("32000"),
        pay_period=PayPeriod.MONTHLY,
        tax_year=2025,
        net_amount=breakdown.net_annual,
        total_deductions=breakdown.total_deductions,
        breakdown=breakdown.to_dict(),
        is_active=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_posting_produces_a_balanced_multi_line_entry(db_session, chart, user_id, profile):
    entry, created = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id
    )
    assert created is True
    assert entry.source is EntrySource.PAYSLIP

    debits = sum(line.debit for line in entry.lines)
    credits = sum(line.credit for line in entry.lines)
    assert debits == credits

    # One credit (gross), four statutory debits, one deposit debit.
    assert len([line for line in entry.lines if line.credit]) == 1
    assert len([line for line in entry.lines if line.debit]) == 5


def test_the_deposit_line_matches_the_snapshot_net(db_session, chart, user_id, profile):
    entry, _ = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id
    )
    deposit = next(line for line in entry.lines if line.account_id == chart["1020"].id)
    expected_net = Decimal(
        next(i["amount_period"] for i in profile.breakdown["items"] if i["key"] == "net")
    )
    assert deposit.debit == expected_net


def test_each_deduction_lands_on_its_statutory_account(db_session, chart, user_id, profile):
    entry, _ = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id
    )
    posted = {line.account_id: line.debit for line in entry.lines}
    items = {i["key"]: Decimal(i["amount_period"]) for i in profile.breakdown["items"]}
    for key, code in svc.DEDUCTION_ACCOUNTS.items():
        assert posted[chart[code].id] == items[key], key


def test_reposting_is_idempotent(db_session, chart, user_id, profile):
    first, created_first = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id
    )
    second, created_second = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id
    )
    assert created_first is True
    assert created_second is False
    assert first.id == second.id


def test_net_pay_must_land_in_an_asset_account(db_session, chart, user_id, profile):
    with pytest.raises(JournalError, match="asset account"):
        svc.post_payslip(db_session, user_id, profile, deposit_account_id=chart["5030"].id)


def test_a_profile_without_a_breakdown_is_rejected(db_session, chart, user_id):
    empty = SalaryProfile(
        user_id=user_id,
        label="Empty",
        gross_amount=Decimal("1000"),
        pay_period=PayPeriod.MONTHLY,
        tax_year=2025,
        breakdown={},
    )
    db_session.add(empty)
    db_session.commit()
    with pytest.raises(JournalError, match="no computed breakdown"):
        svc.post_payslip(db_session, user_id, empty, deposit_account_id=chart["1020"].id)


def test_occurred_at_is_honoured(db_session, chart, user_id, profile):
    when = datetime(2026, 6, 1, 9, 0)
    entry, _ = svc.post_payslip(
        db_session, user_id, profile, deposit_account_id=chart["1020"].id, occurred_at=when
    )
    assert entry.occurred_at == when
