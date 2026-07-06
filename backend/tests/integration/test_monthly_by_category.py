"""Integration tests for /analytics/monthly-by-category (the Analytics
stacked-by-category chart), using seed.py's current + prior month demo data.
"""

from __future__ import annotations

from datetime import date


def _month_key(base: date, months_back: int) -> str:
    idx = base.year * 12 + (base.month - 1) - months_back
    y, m = idx // 12, idx % 12 + 1
    return f"{y:04d}-{m:02d}"


def test_monthly_by_category_shape_and_values(seeded_client):
    r = seeded_client.get(
        "/api/v1/analytics/monthly-by-category", params={"currency": "USD", "months": 2}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "USD"

    today = date.today()
    expected_months = [_month_key(today.replace(day=1), 1), _month_key(today.replace(day=1), 0)]
    assert body["months"] == expected_months

    by_name = {s["category_name"]: s["values"] for s in body["series"]}
    assert "Housing" in by_name
    assert [float(v) for v in by_name["Housing"]] == [1500.0, 1500.0]
    assert [float(v) for v in by_name["Groceries"]] == [410.0, 480.0]
    assert [float(v) for v in by_name["Dining"]] == [150.0, 220.0]
    # Category only present in the current month still appears, with a zero
    # for the month it had no spend.
    assert [float(v) for v in by_name["Transport"]] == [0.0, 160.0]


def test_monthly_by_category_excludes_inbound(seeded_client):
    r = seeded_client.get("/api/v1/analytics/monthly-by-category", params={"currency": "USD"})
    names = {s["category_name"] for s in r.json()["series"]}
    assert "Base salary" not in names
    assert "Freelance income" not in names
