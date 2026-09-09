"""Normal-balance arithmetic: assets and expenses grow on the debit side,
liabilities, equity and income on the credit side."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.base import AccountType
from app.services import balances as svc
from app.services.journal import LineInput, post_entry
from tests.conftest import at


@pytest.mark.parametrize(
    ("account_type", "debits", "credits", "expected"),
    [
        (AccountType.ASSET, "1000", "300", "700"),
        (AccountType.EXPENSE, "500", "0", "500"),
        (AccountType.LIABILITY, "200", "900", "700"),
        (AccountType.EQUITY, "0", "5000", "5000"),
        (AccountType.INCOME, "0", "32000", "32000"),
    ],
)
def test_signed_balance_follows_normal_balance(account_type, debits, credits, expected):
    assert svc.signed_balance(account_type, Decimal(debits), Decimal(credits)) == Decimal(expected)


def test_balances_reflect_postings(db_session, chart, user_id):
    post_entry(
        db_session,
        user_id,
        occurred_at=at(3),
        lines=[
            LineInput(account_id=chart["1020"].id, debit=Decimal("32000")),
            LineInput(account_id=chart["4010"].id, credit=Decimal("32000")),
        ],
    )
    post_entry(
        db_session,
        user_id,
        occurred_at=at(4),
        lines=[
            LineInput(account_id=chart["5010"].id, debit=Decimal("9500")),
            LineInput(account_id=chart["1020"].id, credit=Decimal("9500")),
        ],
    )
    rows = {r.code: r for r in svc.account_balances(db_session, user_id)}
    assert rows["1020"].balance == Decimal("22500.00")
    assert rows["4010"].balance == Decimal("32000.00")
    assert rows["5010"].balance == Decimal("9500.00")


def test_a_trial_balance_always_ties(seeded_db, user_id):
    """The classic proof of a sound double-entry ledger."""
    rows = svc.account_balances(seeded_db, user_id, include_archived=True)
    assert sum(r.debits for r in rows) == sum(r.credits for r in rows)


def test_voided_entries_do_not_count(db_session, chart, user_id):
    from app.services.journal import void_entry

    entry = post_entry(
        db_session,
        user_id,
        occurred_at=at(3),
        lines=[
            LineInput(account_id=chart["5010"].id, debit=Decimal("1000")),
            LineInput(account_id=chart["1010"].id, credit=Decimal("1000")),
        ],
    )
    void_entry(db_session, user_id, entry.id)
    rows = {r.code: r for r in svc.account_balances(db_session, user_id)}
    assert rows["5010"].balance == Decimal("0.00")


def test_as_of_restricts_to_earlier_entries(db_session, chart, user_id):
    for day, amount in ((3, "1000"), (20, "500")):
        post_entry(
            db_session,
            user_id,
            occurred_at=at(day),
            lines=[
                LineInput(account_id=chart["5010"].id, debit=Decimal(amount)),
                LineInput(account_id=chart["1010"].id, credit=Decimal(amount)),
            ],
        )
    rows = {r.code: r for r in svc.account_balances(db_session, user_id, as_of=at(10))}
    assert rows["5010"].balance == Decimal("1000.00")


def test_has_postings_detects_usage(db_session, chart, user_id):
    assert svc.has_postings(db_session, chart["5010"].id) is False
    post_entry(
        db_session,
        user_id,
        occurred_at=at(3),
        lines=[
            LineInput(account_id=chart["5010"].id, debit=Decimal("100")),
            LineInput(account_id=chart["1010"].id, credit=Decimal("100")),
        ],
    )
    assert svc.has_postings(db_session, chart["5010"].id) is True


def test_demo_data_never_overdraws_an_asset(seeded_db, user_id):
    """You cannot spend cash you do not have.

    The seed funds each wallet from payroll before spending from it, derived
    from the spending pattern rather than hard-coded — this pins that down, so
    a later edit to the pattern cannot quietly reintroduce a negative wallet.
    """
    from app.models.base import AccountType

    overdrawn = [
        r
        for r in svc.account_balances(seeded_db, user_id)
        if r.type is AccountType.ASSET and r.balance < 0
    ]
    assert not overdrawn, [f"{r.code} {r.name}: {r.balance}" for r in overdrawn]
