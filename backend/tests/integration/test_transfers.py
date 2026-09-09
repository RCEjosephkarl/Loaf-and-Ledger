"""Transfers are not spending.

The old single-entry schema had a "Savings & investment" expense category, so
money set aside counted against you twice: once as an expense, once as a lower
savings rate. Double entry makes a transfer structurally distinct, and these
tests pin that down.
"""

from __future__ import annotations

from decimal import Decimal


def _overview(client, **params):
    return client.get("/api/v1/analytics/overview", params=params).json()


def test_a_savings_transfer_is_not_an_expense(seeded_client, chart):
    window = {"start": "2026-06-01", "end": "2026-06-30"}
    before = _overview(seeded_client, **window)

    response = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "transfer",
            "amount": "8000.00",
            "account_id": chart["1030"].id,
            "counter_account_id": chart["1020"].id,
            "occurred_at": "2026-06-20T20:00:00",
            "memo": "Move to savings",
        },
    )
    assert response.status_code == 201

    after = _overview(seeded_client, **window)
    assert Decimal(after["total_expense"]) == Decimal(before["total_expense"])
    assert Decimal(after["total_income"]) == Decimal(before["total_income"])
    assert Decimal(after["net_cashflow"]) == Decimal(before["net_cashflow"])
    assert Decimal(after["savings_rate"]) == Decimal(before["savings_rate"])
    # It is not invisible, though — it is reported as its own figure.
    assert Decimal(after["transfer_volume"]) == Decimal(before["transfer_volume"]) + Decimal("8000")


def test_a_transfer_still_moves_the_account_balances(seeded_client, chart):
    def balance(code: str) -> Decimal:
        rows = seeded_client.get("/api/v1/accounts/balances").json()["accounts"]
        return Decimal(next(r["balance"] for r in rows if r["code"] == code))

    savings_before = balance("1030")
    payroll_before = balance("1020")

    seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "transfer",
            "amount": "8000.00",
            "account_id": chart["1030"].id,
            "counter_account_id": chart["1020"].id,
            "occurred_at": "2026-06-20T20:00:00",
        },
    )

    assert balance("1030") == savings_before + Decimal("8000.00")
    assert balance("1020") == payroll_before - Decimal("8000.00")


def test_transfers_are_flagged_in_the_fact_table(seeded_client, chart):
    from app.warehouse.engine import cursor

    entry = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "transfer",
            "amount": "1000.00",
            "account_id": chart["1090"].id,
            "counter_account_id": chart["1030"].id,
            "occurred_at": "2026-06-20T20:00:00",
        },
    ).json()

    with cursor() as conn:
        flags = conn.execute(
            "SELECT DISTINCT is_transfer FROM fact_ledger_line WHERE entry_id = ?", [entry["id"]]
        ).fetchall()
    assert flags == [(True,)]


def test_there_is_no_savings_expense_account(seeded_client):
    """The defect's root cause, asserted away: putting money aside must not be
    expressible as an expense in the seeded chart."""
    accounts = seeded_client.get("/api/v1/accounts").json()
    expense_names = {a["name"].lower() for a in accounts if a["type"] == "expense"}
    assert not any("saving" in name or "investment" in name for name in expense_names)
