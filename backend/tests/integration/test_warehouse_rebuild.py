"""A full rebuild must reproduce exactly what write-through produced."""

from __future__ import annotations

from app.warehouse.engine import cursor


def _snapshot() -> dict:
    with cursor() as conn:
        return {
            "facts": conn.execute(
                "SELECT line_id, entry_id, date_key, account_key, debit, credit, "
                "signed_amount, is_transfer FROM fact_ledger_line ORDER BY line_id"
            ).fetchall(),
            "monthly": conn.execute(
                "SELECT month_key, account_key, inflow, outflow, net_amount, entry_count "
                "FROM agg_monthly_account ORDER BY month_key, account_key"
            ).fetchall(),
            "daily": conn.execute(
                "SELECT date_key, inflow, outflow, net, cumulative_balance "
                "FROM agg_daily_cashflow ORDER BY date_key"
            ).fetchall(),
        }


def test_rebuild_matches_write_through(seeded_client, chart):
    """Post a few entries through the API, then rebuild from scratch and check
    the two paths agree row for row."""
    for payload in (
        {"kind": "income", "amount": "4000.00", "account_id": chart["1020"].id,
         "counter_account_id": chart["4050"].id, "occurred_at": "2026-06-10T10:00:00"},
        {"kind": "expense", "amount": "780.00", "account_id": chart["1010"].id,
         "counter_account_id": chart["5040"].id, "occurred_at": "2026-06-12T19:00:00"},
        {"kind": "transfer", "amount": "2500.00", "account_id": chart["1030"].id,
         "counter_account_id": chart["1020"].id, "occurred_at": "2026-06-28T20:00:00"},
    ):
        assert seeded_client.post("/api/v1/ledger/entries/simple", json=payload).status_code == 201

    incremental = _snapshot()

    response = seeded_client.post("/api/v1/warehouse/rebuild")
    assert response.status_code == 200
    assert response.json()["counts"]["fact_ledger_line"] == len(incremental["facts"])

    assert _snapshot() == incremental


def test_rebuild_leaves_no_drift(seeded_client):
    seeded_client.post("/api/v1/warehouse/rebuild")
    status = seeded_client.get("/api/v1/warehouse/status").json()
    assert status["drift"] == 0
    assert status["is_stale"] is False
    assert status["integrity_problems"] == []
    assert status["ok"] is True


def test_voided_entries_are_excluded_from_a_rebuild(seeded_client, chart):
    entry = seeded_client.post(
        "/api/v1/ledger/entries/simple",
        json={"kind": "expense", "amount": "600.00", "account_id": chart["1010"].id,
              "counter_account_id": chart["5040"].id, "occurred_at": "2026-06-12T19:00:00"},
    ).json()
    seeded_client.delete(f"/api/v1/ledger/entries/{entry['id']}")
    seeded_client.post("/api/v1/warehouse/rebuild")

    with cursor() as conn:
        rows = conn.execute(
            "SELECT count(*) FROM fact_ledger_line WHERE entry_id = ?", [entry["id"]]
        ).fetchone()
    assert rows[0] == 0
    assert seeded_client.get("/api/v1/warehouse/status").json()["drift"] == 0
