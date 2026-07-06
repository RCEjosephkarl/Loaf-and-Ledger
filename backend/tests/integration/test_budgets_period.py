"""Integration tests for the period-scoped /budgets/status endpoint.

Relies on seed.py's demo data: a Groceries budget in the current month (500)
and the two prior months (480, 480), with Groceries spend of 480 (current
month) and 410 (prior month) — the month before that has no transactions.
"""

from __future__ import annotations

from datetime import date


def _months_back(base: date, n: int) -> tuple[int, int]:
    idx = base.year * 12 + (base.month - 1) - n
    return idx // 12, idx % 12 + 1


def test_status_3m_aggregates_limits_and_spend_across_months(seeded_client):
    status = seeded_client.get("/api/v1/budgets/status", params={"scope": "3m"}).json()
    groceries = next(s for s in status if s["category_name"] == "Groceries")

    assert groceries["scope"] == "3m"
    assert groceries["year"] is None
    assert groceries["month"] is None
    assert float(groceries["limit_amount"]) == 1460.0  # 500 + 480 + 480
    assert float(groceries["spent"]) == 890.0  # 480 (this month) + 410 (prior month)


def test_status_ytd_only_includes_months_within_the_current_year(seeded_client):
    today = date.today()
    status = seeded_client.get("/api/v1/budgets/status", params={"scope": "ytd"}).json()
    groceries = next(s for s in status if s["category_name"] == "Groceries")

    assert groceries["scope"] == "ytd"
    y0, _ = _months_back(today.replace(day=1), 2)
    expected_limit = 1460.0 if y0 == today.year else 980.0  # drop the month-2 budget if it's last year
    assert float(groceries["limit_amount"]) == expected_limit


def test_status_all_scope_spans_every_budgeted_month(seeded_client):
    status = seeded_client.get("/api/v1/budgets/status", params={"scope": "all"}).json()
    groceries = next(s for s in status if s["category_name"] == "Groceries")

    assert groceries["scope"] == "all"
    assert float(groceries["limit_amount"]) == 1460.0
    assert float(groceries["spent"]) == 890.0


def test_status_legacy_year_month_is_unchanged(seeded_client):
    today = date.today()
    status = seeded_client.get(
        "/api/v1/budgets/status", params={"year": today.year, "month": today.month}
    ).json()
    groceries = next(s for s in status if s["category_name"] == "Groceries")

    assert groceries["scope"] == "month"
    assert groceries["year"] == today.year
    assert groceries["month"] == today.month
    assert float(groceries["limit_amount"]) == 500.0
    assert float(groceries["spent"]) == 480.0


def test_status_requires_scope_or_year_and_month(seeded_client):
    r = seeded_client.get("/api/v1/budgets/status")
    assert r.status_code == 422


def test_status_multi_month_currency_conversion_uses_latest_month(client):
    """A category budgeted in two currencies across months converts every
    row into the *latest* month's currency (documented policy)."""
    cats = client.get("/api/v1/ledger/categories", params={"direction": "outbound"}).json()
    dining = next(c for c in cats if c["name"] == "Dining")
    today = date.today()
    y0, m0 = _months_back(today.replace(day=1), 1)

    client.post(
        "/api/v1/budgets",
        json={"category_id": dining["id"], "year": y0, "month": m0, "limit_amount": "5800", "currency": "PHP"},
    )
    client.post(
        "/api/v1/budgets",
        json={
            "category_id": dining["id"],
            "year": today.year,
            "month": today.month,
            "limit_amount": "100",
            "currency": "USD",
        },
    )

    status = client.get("/api/v1/budgets/status", params={"scope": "3m"}).json()
    dining_status = next(s for s in status if s["category_name"] == "Dining")
    assert dining_status["currency"] == "USD"
    # 5800 PHP -> ~100 USD (seed rate: 1 USD = 58 PHP) + 100 USD current = ~200
    assert abs(float(dining_status["limit_amount"]) - 200.0) < 0.5
