"""The balance invariant — the property that makes this a ledger."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.base import EntrySource
from app.services import journal as svc
from tests.conftest import at


def L(account, debit="0", credit="0", memo=None):  # noqa: N802 - terse test helper
    return svc.LineInput(
        account_id=account.id, debit=Decimal(debit), credit=Decimal(credit), memo=memo
    )


def test_balanced_entry_posts(db_session, chart, user_id):
    entry = svc.post_entry(
        db_session,
        user_id,
        occurred_at=at(3),
        lines=[L(chart["5030"], debit="1200"), L(chart["1010"], credit="1200")],
        memo="Groceries",
    )
    assert entry.id is not None
    assert len(entry.lines) == 2
    assert sum(line.debit for line in entry.lines) == sum(line.credit for line in entry.lines)


def test_unbalanced_entry_is_rejected(db_session, chart, user_id):
    with pytest.raises(svc.UnbalancedEntry, match="does not balance"):
        svc.post_entry(
            db_session,
            user_id,
            occurred_at=at(3),
            lines=[L(chart["5030"], debit="1200"), L(chart["1010"], credit="900")],
        )


def test_two_sided_line_is_rejected(db_session, chart, user_id):
    with pytest.raises(svc.JournalError, match="not both"):
        svc.post_entry(
            db_session,
            user_id,
            occurred_at=at(3),
            lines=[L(chart["5030"], debit="100", credit="100"), L(chart["1010"], credit="100")],
        )


def test_zero_line_is_rejected(db_session, chart, user_id):
    with pytest.raises(svc.JournalError, match="must carry an amount"):
        svc.post_entry(
            db_session,
            user_id,
            occurred_at=at(3),
            lines=[L(chart["5030"]), L(chart["1010"], credit="100")],
        )


def test_single_line_is_rejected(db_session, chart, user_id):
    with pytest.raises(svc.JournalError, match="at least two lines"):
        svc.post_entry(
            db_session, user_id, occurred_at=at(3), lines=[L(chart["5030"], debit="100")]
        )


def test_multi_line_entry_balances(db_session, chart, user_id):
    """A payslip-shaped entry: four debits against one credit."""
    entry = svc.post_entry(
        db_session,
        user_id,
        occurred_at=at(1),
        lines=[
            L(chart["6020"], debit="1350"),
            L(chart["6030"], debit="800"),
            L(chart["6040"], debit="100"),
            L(chart["1020"], debit="29750"),
            L(chart["4010"], credit="32000"),
        ],
    )
    assert len(entry.lines) == 5
    assert [line.line_no for line in entry.lines] == [1, 2, 3, 4, 5]


class TestSimpleEntry:
    """The quick-entry form must put each side on the correct ledger side."""

    def test_expense_debits_the_expense_account(self, db_session, chart, user_id):
        entry = svc.simple_entry(
            db_session,
            user_id,
            kind="expense",
            amount=Decimal("500"),
            account_id=chart["1010"].id,
            counter_account_id=chart["5040"].id,
            occurred_at=at(5),
        )
        by_account = {line.account_id: line for line in entry.lines}
        assert by_account[chart["5040"].id].debit == Decimal("500.00")
        assert by_account[chart["1010"].id].credit == Decimal("500.00")

    def test_income_credits_the_income_account(self, db_session, chart, user_id):
        entry = svc.simple_entry(
            db_session,
            user_id,
            kind="income",
            amount=Decimal("6500"),
            account_id=chart["1040"].id,
            counter_account_id=chart["4050"].id,
            occurred_at=at(5),
        )
        by_account = {line.account_id: line for line in entry.lines}
        assert by_account[chart["1040"].id].debit == Decimal("6500.00")
        assert by_account[chart["4050"].id].credit == Decimal("6500.00")

    def test_transfer_moves_between_assets(self, db_session, chart, user_id):
        entry = svc.simple_entry(
            db_session,
            user_id,
            kind="transfer",
            amount=Decimal("5000"),
            account_id=chart["1030"].id,
            counter_account_id=chart["1020"].id,
            occurred_at=at(27),
        )
        assert entry.source is EntrySource.TRANSFER
        by_account = {line.account_id: line for line in entry.lines}
        assert by_account[chart["1030"].id].debit == Decimal("5000.00")
        assert by_account[chart["1020"].id].credit == Decimal("5000.00")

    def test_expense_against_a_non_expense_account_is_rejected(self, db_session, chart, user_id):
        with pytest.raises(svc.JournalError, match="not an expense account"):
            svc.simple_entry(
                db_session,
                user_id,
                kind="expense",
                amount=Decimal("100"),
                account_id=chart["1010"].id,
                counter_account_id=chart["4010"].id,
                occurred_at=at(5),
            )

    def test_money_side_must_be_a_balance_sheet_account(self, db_session, chart, user_id):
        with pytest.raises(svc.JournalError, match="must be an asset or liability"):
            svc.simple_entry(
                db_session,
                user_id,
                kind="expense",
                amount=Decimal("100"),
                account_id=chart["5030"].id,
                counter_account_id=chart["5040"].id,
                occurred_at=at(5),
            )

    def test_same_account_both_sides_is_rejected(self, db_session, chart, user_id):
        with pytest.raises(svc.JournalError, match="same account"):
            svc.simple_entry(
                db_session,
                user_id,
                kind="transfer",
                amount=Decimal("100"),
                account_id=chart["1010"].id,
                counter_account_id=chart["1010"].id,
                occurred_at=at(5),
            )


def test_void_is_soft(db_session, chart, user_id):
    entry = svc.simple_entry(
        db_session,
        user_id,
        kind="expense",
        amount=Decimal("300"),
        account_id=chart["1010"].id,
        counter_account_id=chart["5040"].id,
        occurred_at=at(5),
    )
    svc.void_entry(db_session, user_id, entry.id)
    # The row survives — a ledger you can silently erase from is not auditable.
    assert svc.get_entry(db_session, user_id, entry.id).voided_at is not None


def test_voided_entry_cannot_be_amended(db_session, chart, user_id):
    entry = svc.simple_entry(
        db_session,
        user_id,
        kind="expense",
        amount=Decimal("300"),
        account_id=chart["1010"].id,
        counter_account_id=chart["5040"].id,
        occurred_at=at(5),
    )
    svc.void_entry(db_session, user_id, entry.id)
    with pytest.raises(svc.JournalError, match="voided"):
        svc.update_entry(db_session, user_id, entry.id, memo="nope")


def test_update_replaces_the_whole_line_set(db_session, chart, user_id):
    entry = svc.simple_entry(
        db_session,
        user_id,
        kind="expense",
        amount=Decimal("300"),
        account_id=chart["1010"].id,
        counter_account_id=chart["5040"].id,
        occurred_at=at(5),
    )
    updated = svc.update_entry(
        db_session,
        user_id,
        entry.id,
        lines=[L(chart["5030"], debit="450"), L(chart["1040"], credit="450")],
    )
    assert len(updated.lines) == 2
    assert {line.account_id for line in updated.lines} == {chart["5030"].id, chart["1040"].id}


def test_update_to_an_unbalanced_set_is_rejected(db_session, chart, user_id):
    entry = svc.simple_entry(
        db_session,
        user_id,
        kind="expense",
        amount=Decimal("300"),
        account_id=chart["1010"].id,
        counter_account_id=chart["5040"].id,
        occurred_at=at(5),
    )
    with pytest.raises(svc.UnbalancedEntry):
        svc.update_entry(
            db_session,
            user_id,
            entry.id,
            lines=[L(chart["5030"], debit="450"), L(chart["1040"], credit="400")],
        )


def test_integrity_check_is_clean_on_a_seeded_ledger(seeded_db, user_id):
    assert svc.integrity_check(seeded_db, user_id) == []
