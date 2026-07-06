"""Integration tests for the /budgets/fund "initial fund" endpoints.

Relies on seed.py's demo data: the prior calendar month has Base salary
(4590 inbound) and Housing/Groceries/Dining (1500+410+150=2060 outbound),
net 2530, and nothing earlier — so the carry-over default for the current
month is exactly that prior month's ending balance.
"""

from __future__ import annotations


def test_fund_default_is_carry_over_from_prior_period(seeded_client):
    r = seeded_client.get("/api/v1/budgets/fund", params={"scope": "month", "currency": "USD"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_override"] is False
    assert body["scope"] == "month"
    assert abs(float(body["amount"]) - 2530.0) < 0.01


def test_fund_all_scope_default_is_zero(seeded_client):
    r = seeded_client.get("/api/v1/budgets/fund", params={"scope": "all", "currency": "USD"})
    assert r.status_code == 200
    assert float(r.json()["amount"]) == 0.0
    assert r.json()["is_override"] is False


def test_fund_override_persists_and_resets(seeded_client):
    post = seeded_client.post(
        "/api/v1/budgets/fund", json={"scope": "month", "amount": "1000", "currency": "USD"}
    )
    assert post.status_code == 200
    assert post.json()["is_override"] is True
    assert float(post.json()["amount"]) == 1000.0

    get = seeded_client.get("/api/v1/budgets/fund", params={"scope": "month", "currency": "USD"})
    assert get.json()["is_override"] is True
    assert float(get.json()["amount"]) == 1000.0

    delete = seeded_client.delete("/api/v1/budgets/fund", params={"scope": "month"})
    assert delete.status_code == 204

    reverted = seeded_client.get("/api/v1/budgets/fund", params={"scope": "month", "currency": "USD"})
    assert reverted.json()["is_override"] is False
    assert abs(float(reverted.json()["amount"]) - 2530.0) < 0.01


def test_fund_override_upsert_updates_existing(seeded_client):
    seeded_client.post("/api/v1/budgets/fund", json={"scope": "ytd", "amount": "500", "currency": "USD"})
    second = seeded_client.post(
        "/api/v1/budgets/fund", json={"scope": "ytd", "amount": "750", "currency": "USD"}
    )
    assert second.status_code == 200
    assert float(second.json()["amount"]) == 750.0

    get = seeded_client.get("/api/v1/budgets/fund", params={"scope": "ytd", "currency": "USD"})
    assert float(get.json()["amount"]) == 750.0
