"""Coherence: an OLTP write must be visible in OLAP analytics immediately.

This is the requirement the write-through ETL exists to satisfy. Every test
here posts through the API and then reads analytics *with no refresh call in
between* — if write-through regresses, these fail.
"""

from __future__ import annotations

from decimal import Decimal

from app.warehouse.engine import cursor


def _fact_rows(entry_id: int) -> list[tuple]:
    with cursor() as conn:
        return conn.execute(
            "SELECT account_key, debit, credit, is_transfer FROM fact_ledger_line "
            "WHERE entry_id = ? ORDER BY line_id",
            [entry_id],
        ).fetchall()


def _overview(client, **params):
    response = client.get("/api/v1/analytics/overview", params=params)
    assert response.status_code == 200
    return response.json()


def test_new_earning_reaches_analytics_without_a_refresh(seeded_client, chart):
    before = Decimal(_overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_income"])

    response = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "income",
            "amount": "5000.00",
            "account_id": chart["1020"].id,
            "counter_account_id": chart["4050"].id,
            "occurred_at": "2026-06-15T10:00:00",
            "memo": "Coherence check",
        },
    )
    assert response.status_code == 201, response.text
    entry_id = response.json()["id"]

    # 1. It is in the OLAP atomic fact.
    rows = _fact_rows(entry_id)
    assert len(rows) == 2
    assert not any(row[3] for row in rows)  # income is not a transfer

    # 2. And in the aggregate the analytics endpoint reads.
    after = Decimal(_overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_income"])
    assert after == before + Decimal("5000.00")

    # 3. With no drift between the stores.
    status = seeded_client.get("/api/v1/warehouse/status").json()
    assert status["drift"] == 0
    assert status["ok"] is True


def test_expense_reaches_analytics(seeded_client, chart):
    before = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )
    response = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "expense",
            "amount": "1250.00",
            "account_id": chart["1010"].id,
            "counter_account_id": chart["5040"].id,
            "occurred_at": "2026-06-15T19:30:00",
        },
    )
    assert response.status_code == 201
    after = Decimal(_overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"])
    assert after == before + Decimal("1250.00")


def test_edit_moves_the_warehouse_figures(seeded_client, chart):
    created = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "expense",
            "amount": "1000.00",
            "account_id": chart["1010"].id,
            "counter_account_id": chart["5040"].id,
            "occurred_at": "2026-06-15T19:30:00",
        },
    ).json()
    before = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )

    patched = seeded_client.patch(
        f"/api/v1/ledger/entries/{created['id']}",
        json={
            "lines": [
                {"account_id": chart["5040"].id, "debit": "1600.00"},
                {"account_id": chart["1010"].id, "credit": "1600.00"},
            ]
        },
    )
    assert patched.status_code == 200, patched.text

    after = Decimal(_overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"])
    assert after == before + Decimal("600.00")
    assert len(_fact_rows(created["id"])) == 2  # replaced, not duplicated
    assert seeded_client.get("/api/v1/warehouse/status").json()["drift"] == 0


def test_void_removes_the_entry_from_analytics(seeded_client, chart):
    created = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "expense",
            "amount": "2000.00",
            "account_id": chart["1010"].id,
            "counter_account_id": chart["5040"].id,
            "occurred_at": "2026-06-15T19:30:00",
        },
    ).json()
    with_entry = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )

    assert seeded_client.delete(f"/api/v1/ledger/entries/{created['id']}").status_code == 204

    without = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )
    assert without == with_entry - Decimal("2000.00")
    assert _fact_rows(created["id"]) == []
    assert seeded_client.get("/api/v1/warehouse/status").json()["drift"] == 0


def test_moving_an_entrys_date_moves_its_rollup(seeded_client, chart):
    """The old month must be refreshed too, or the rollup strands a stale row."""
    created = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={
            "kind": "expense",
            "amount": "900.00",
            "account_id": chart["1010"].id,
            "counter_account_id": chart["5040"].id,
            "occurred_at": "2026-06-15T19:30:00",
        },
    ).json()
    june_before = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )
    july_before = Decimal(
        _overview(seeded_client, start="2026-07-01", end="2026-07-31")["total_expense"]
    )

    seeded_client.patch(
        f"/api/v1/ledger/entries/{created['id']}", json={"occurred_at": "2026-07-15T19:30:00"}
    )

    june_after = Decimal(
        _overview(seeded_client, start="2026-06-01", end="2026-06-30")["total_expense"]
    )
    july_after = Decimal(
        _overview(seeded_client, start="2026-07-01", end="2026-07-31")["total_expense"]
    )
    assert june_after == june_before - Decimal("900.00")
    assert july_after == july_before + Decimal("900.00")


def test_payslip_posting_reaches_the_ledger_and_the_warehouse(seeded_client, chart):
    profile = seeded_client.get("/api/v1/salary/profiles/active").json()
    response = seeded_client.post(
        f"/api/v1/salary/profiles/{profile['id']}/post",
        json={"deposit_account_id": chart["1020"].id, "occurred_at": "2026-06-01T09:00:00"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True

    entry = body["entry"]
    debits = sum(Decimal(line["debit"]) for line in entry["lines"])
    credits = sum(Decimal(line["credit"]) for line in entry["lines"])
    assert debits == credits

    assert len(_fact_rows(entry["id"])) == len(entry["lines"])

    # Re-posting is a no-op, not a duplicate.
    again = seeded_client.post(
        f"/api/v1/salary/profiles/{profile['id']}/post",
        json={"deposit_account_id": chart["1020"].id},
    ).json()
    assert again["created"] is False
    assert again["entry"]["id"] == entry["id"]
