"""Integration tests for /api/v1/system (database inspector, baseline reset, seed, deletion)."""

from __future__ import annotations


def test_database_overview_and_preview(seeded_client):
    res = seeded_client.get("/api/v1/system/database")
    assert res.status_code == 200
    data = res.json()
    assert data["oltp_engine"] == "sqlite"
    assert data["warehouse_ok"] is True
    assert data["warehouse_drift"] == 0
    table_map = {t["name"]: t for t in data["tables"]}
    assert table_map["accounts"]["row_count"] == 36
    assert table_map["journal_entries"]["row_count"] > 0
    assert table_map["fact_ledger_line"]["row_count"] > 0

    # Preview OLTP table
    prev_oltp = seeded_client.get("/api/v1/system/database/preview/accounts?limit=5")
    assert prev_oltp.status_code == 200
    p_data = prev_oltp.json()
    assert p_data["store"] == "oltp"
    assert p_data["total_rows"] == 36
    assert len(p_data["rows"]) == 5
    assert "code" in p_data["columns"]

    # Preview OLAP table
    prev_olap = seeded_client.get("/api/v1/system/database/preview/dim_account?limit=5")
    assert prev_olap.status_code == 200
    o_data = prev_olap.json()
    assert o_data["store"] == "olap"
    assert o_data["total_rows"] == 36
    assert len(o_data["rows"]) == 5

    # Unknown table is rejected with 404
    bad = seeded_client.get("/api/v1/system/database/preview/not_a_table")
    assert bad.status_code == 404


def test_reset_baseline_and_reseed_demo(seeded_client):
    res = seeded_client.post("/api/v1/system/reset-baseline")
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "reset_baseline"
    assert body["counts"]["accounts"] == 36
    assert body["counts"]["journal_entries"] == 0
    assert body["counts"]["journal_lines"] == 0
    assert body["counts"]["budgets"] == 0
    assert body["counts"]["salary_profiles"] == 0
    assert body["warehouse_counts"]["fact_ledger_line"] == 0

    # Seed demo back via API
    seed_res = seeded_client.post("/api/v1/system/seed-demo")
    assert seed_res.status_code == 200
    s_body = seed_res.json()
    assert s_body["counts"]["journal_entries"] > 0
    assert s_body["warehouse_counts"]["fact_ledger_line"] > 0


def test_granular_data_deletion(seeded_client):
    # Delete budgets only
    res = seeded_client.post("/api/v1/system/delete-data", json={"target": "budgets"})
    assert res.status_code == 200
    assert res.json()["counts"]["budgets"] == 0
    assert res.json()["counts"]["journal_entries"] > 0

    # Delete salary profiles only
    res2 = seeded_client.post("/api/v1/system/delete-data", json={"target": "salary_profiles"})
    assert res2.status_code == 200
    assert res2.json()["counts"]["salary_profiles"] == 0
    assert res2.json()["warehouse_counts"]["fact_payslip_item"] == 0

    # Delete entries only
    res3 = seeded_client.post("/api/v1/system/delete-data", json={"target": "entries"})
    assert res3.status_code == 200
    assert res3.json()["counts"]["journal_entries"] == 0
    assert res3.json()["warehouse_counts"]["fact_ledger_line"] == 0
