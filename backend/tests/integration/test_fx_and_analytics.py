"""Integration tests for the FX-rates endpoint, running balance, and FX CSV export.

The FX endpoints are monkeypatched at `fx_live.fetch_series` so the suite never
makes a real network call.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services import fx_live

FAKE_SERIES = {
    date(2026, 7, 1): {"PHP": Decimal("58.50"), "AUD": Decimal("1.50"), "EUR": Decimal("0.91")},
    date(2026, 7, 2): {"PHP": Decimal("58.70"), "AUD": Decimal("1.51"), "EUR": Decimal("0.90")},
}


def test_fx_rates_endpoint_upserts_and_returns_series(seeded_client, monkeypatch):
    monkeypatch.setattr(fx_live, "fetch_series", lambda *a, **k: FAKE_SERIES)

    r = seeded_client.get("/api/v1/fx/rates", params={"base": "USD"})
    assert r.status_code == 200
    body = r.json()
    assert body["base"] == "USD"
    assert body["live"] is True
    assert set(body["quotes"]) == {"PHP", "AUD", "EUR"}
    dates = {p["date"] for p in body["series"]}
    assert {"2026-07-01", "2026-07-02"} <= dates
    latest = next(p for p in body["series"] if p["date"] == "2026-07-02")
    assert float(latest["rates"]["PHP"]) == 58.7


def test_fx_rates_endpoint_respects_explicit_range(seeded_client, monkeypatch):
    captured = {}

    def _fake_fetch(base, quotes, start, end):
        captured["start"], captured["end"] = start, end
        return FAKE_SERIES

    monkeypatch.setattr(fx_live, "fetch_series", _fake_fetch)

    r = seeded_client.get(
        "/api/v1/fx/rates", params={"base": "USD", "start": "2026-07-01", "end": "2026-07-02"}
    )
    assert r.status_code == 200
    assert captured["start"] == date(2026, 7, 1)
    assert captured["end"] == date(2026, 7, 2)


def test_fx_rates_endpoint_defaults_to_seven_days_without_range(seeded_client, monkeypatch):
    captured = {}

    def _fake_fetch(base, quotes, start, end):
        captured["start"], captured["end"] = start, end
        return FAKE_SERIES

    monkeypatch.setattr(fx_live, "fetch_series", _fake_fetch)

    r = seeded_client.get("/api/v1/fx/rates", params={"base": "USD"})
    assert r.status_code == 200
    assert (captured["end"] - captured["start"]).days == fx_live.HISTORY_DAYS - 1


def test_running_balance_matches_dashboard_net_cashflow(seeded_client):
    r = seeded_client.get("/api/v1/analytics/running-balance", params={"currency": "USD"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert points

    running_total = Decimal("0")
    for p in points:
        running_total += Decimal(p["net"])
        assert Decimal(p["balance"]) == running_total

    summary = seeded_client.get("/api/v1/dashboard/summary", params={"currency": "USD"}).json()
    assert Decimal(points[-1]["balance"]) == Decimal(summary["net_cashflow"])


def test_export_fx_rates_csv(seeded_client, monkeypatch):
    monkeypatch.setattr(fx_live, "fetch_series", lambda *a, **k: FAKE_SERIES)
    seeded_client.get("/api/v1/fx/rates", params={"base": "USD"})  # populate history

    r = seeded_client.get("/api/v1/export/fx-rates.csv", params={"base": "USD"})
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert lines[0] == "date,base_currency,quote_currency,rate"
    assert any(",PHP," in line for line in lines[1:])


def test_transaction_occurred_time_roundtrip(client):
    cats = client.get("/api/v1/ledger/categories", params={"direction": "outbound"}).json()
    groceries = next(c for c in cats if c["name"] == "Groceries")

    r = client.post(
        "/api/v1/ledger/transactions",
        json={
            "direction": "outbound",
            "category_id": groceries["id"],
            "amount": "12.50",
            "currency": "USD",
            "occurred_on": str(date.today()),
            "occurred_time": "14:32",
            "description": "Coffee",
        },
    )
    assert r.status_code == 201
    assert r.json()["occurred_time"] == "14:32:00"
