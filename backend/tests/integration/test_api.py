"""API integration tests (FastAPI TestClient on SQLite)."""

from __future__ import annotations

from datetime import date


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_regions_lists_four(client):
    regions = {r["region"] for r in client.get("/api/v1/regions").json()}
    assert regions == {"PH", "US", "AU", "EU"}


def test_salary_calculate_does_not_persist(client):
    r = client.post(
        "/api/v1/salary/calculate",
        json={"region": "US", "gross_amount": "6000", "pay_period": "monthly"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "USD"
    assert float(body["net_period"]) < 6000
    # nothing persisted
    assert client.get("/api/v1/salary/profiles").json() == []


def test_create_and_activate_salary_profile(client):
    r = client.post(
        "/api/v1/salary/profiles",
        json={"label": "Job", "region": "AU", "gross_amount": "9000", "pay_period": "monthly"},
    )
    assert r.status_code == 201
    active = client.get("/api/v1/salary/profiles/active").json()
    assert active["label"] == "Job"
    assert active["region"] == "AU"
    assert active["breakdown"]["region"] == "AU"


def test_transaction_flow_and_category_direction_guard(client):
    cats = client.get("/api/v1/ledger/categories", params={"direction": "outbound"}).json()
    groceries = next(c for c in cats if c["name"] == "Groceries")

    ok = client.post(
        "/api/v1/ledger/transactions",
        json={
            "direction": "outbound",
            "category_id": groceries["id"],
            "amount": "120.50",
            "region": "US",
            "occurred_on": str(date.today()),
        },
    )
    assert ok.status_code == 201
    assert ok.json()["currency"] == "USD"  # resolved from region

    # Mismatched direction is rejected.
    bad = client.post(
        "/api/v1/ledger/transactions",
        json={
            "direction": "inbound",
            "category_id": groceries["id"],
            "amount": "10",
            "occurred_on": str(date.today()),
        },
    )
    assert bad.status_code == 422


def test_update_transaction(client):
    cats = client.get("/api/v1/ledger/categories", params={"direction": "outbound"}).json()
    groceries = next(c for c in cats if c["name"] == "Groceries")
    dining = next(c for c in cats if c["name"] == "Dining")

    created = client.post(
        "/api/v1/ledger/transactions",
        json={
            "direction": "outbound",
            "category_id": groceries["id"],
            "amount": "50.00",
            "currency": "USD",
            "occurred_on": str(date.today()),
            "description": "Original",
        },
    ).json()

    patched = client.patch(
        f"/api/v1/ledger/transactions/{created['id']}",
        json={"category_id": dining["id"], "amount": "75.25", "description": "Updated"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["category_id"] == dining["id"]
    assert float(body["amount"]) == 75.25
    assert body["description"] == "Updated"
    # Fields not included in the patch are untouched.
    assert body["currency"] == "USD"
    assert body["occurred_on"] == str(date.today())

    missing = client.patch("/api/v1/ledger/transactions/999999", json={"amount": "1"})
    assert missing.status_code == 404


def test_dashboard_currency_conversion(seeded_client):
    usd = seeded_client.get("/api/v1/dashboard/summary", params={"currency": "USD"}).json()
    php = seeded_client.get("/api/v1/dashboard/summary", params={"currency": "PHP"}).json()
    assert float(usd["total_income"]) > 0
    # 1 USD = 58 PHP in seed data
    assert abs(float(php["total_income"]) - float(usd["total_income"]) * 58) < 1.0
    assert php["currency"] == "PHP"
    assert len(usd["insights"]) >= 1


def test_budget_upsert_and_status(seeded_client):
    cats = seeded_client.get("/api/v1/ledger/categories", params={"direction": "outbound"}).json()
    dining = next(c for c in cats if c["name"] == "Dining")
    today = date.today()
    up = seeded_client.post(
        "/api/v1/budgets",
        json={
            "category_id": dining["id"],
            "year": today.year,
            "month": today.month,
            "limit_amount": "300",
        },
    )
    assert up.status_code == 201
    # upsert: second call updates, not duplicates
    seeded_client.post(
        "/api/v1/budgets",
        json={
            "category_id": dining["id"],
            "year": today.year,
            "month": today.month,
            "limit_amount": "350",
        },
    )
    budgets = seeded_client.get("/api/v1/budgets").json()
    dining_budgets = [b for b in budgets if b["category_id"] == dining["id"]]
    assert len(dining_budgets) == 1
    assert float(dining_budgets[0]["limit_amount"]) == 350.0

    status = seeded_client.get(
        "/api/v1/budgets/status", params={"year": today.year, "month": today.month}
    ).json()
    assert any(s["category_name"] == "Groceries" for s in status)


def test_csv_export(seeded_client):
    r = seeded_client.get("/api/v1/export/expenses.csv", params={"currency": "USD"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("date,category,direction,amount,currency")
    assert "amount_USD" in lines[0]
    assert len(lines) > 1
