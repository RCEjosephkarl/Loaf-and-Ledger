"""Unit tests for the Frankfurter FX client (services/fx_live.py) — no network."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx

from app.services import fx_live


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def test_fetch_series_parses_rates(monkeypatch):
    payload = {
        "amount": 1.0,
        "base": "USD",
        "start_date": "2026-06-29",
        "end_date": "2026-07-03",
        "rates": {
            "2026-06-29": {"AUD": 1.4493, "EUR": 0.87673, "PHP": 61.184},
            "2026-07-03": {"AUD": 1.4413, "EUR": 0.87352, "PHP": 61.442},
        },
    }
    monkeypatch.setattr(fx_live.httpx, "get", lambda *a, **k: _FakeResponse(payload))

    series = fx_live.fetch_series(
        "USD", ["AUD", "EUR", "PHP"], date(2026, 6, 29), date(2026, 7, 3)
    )

    assert series[date(2026, 6, 29)]["AUD"] == Decimal("1.4493")
    assert series[date(2026, 7, 3)]["PHP"] == Decimal("61.442")


def test_fetch_series_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(fx_live.httpx, "get", _raise)

    assert fx_live.fetch_series("USD", ["AUD"], date(2026, 6, 29), date(2026, 7, 3)) is None


def test_fetch_series_returns_none_on_malformed_payload(monkeypatch):
    monkeypatch.setattr(fx_live.httpx, "get", lambda *a, **k: _FakeResponse({"nope": True}))

    assert fx_live.fetch_series("USD", ["AUD"], date(2026, 6, 29), date(2026, 7, 3)) is None


def test_fetch_series_empty_quotes_short_circuits(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("should not call the network when there are no quotes")

    monkeypatch.setattr(fx_live.httpx, "get", _boom)

    assert fx_live.fetch_series("USD", [], date(2026, 6, 29), date(2026, 7, 3)) == {}


def test_refresh_uses_explicit_range(db_session, monkeypatch):
    captured = {}

    def _fake_fetch(base, quotes, start, end):
        captured["start"], captured["end"] = start, end
        return {start: {q: Decimal("1.0") for q in quotes}}

    monkeypatch.setattr(fx_live, "fetch_series", _fake_fetch)

    result = fx_live.refresh(db_session, "USD", start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert captured["start"] == date(2026, 1, 1)
    assert captured["end"] == date(2026, 1, 31)
    assert result.live is True


def test_refresh_clamps_overly_long_ranges(db_session, monkeypatch):
    captured = {}

    def _fake_fetch(base, quotes, start, end):
        captured["start"], captured["end"] = start, end
        return {start: {q: Decimal("1.0") for q in quotes}}

    monkeypatch.setattr(fx_live, "fetch_series", _fake_fetch)

    end = date(2026, 7, 6)
    start = end - timedelta(days=1000)  # far beyond MAX_HISTORY_DAYS
    fx_live.refresh(db_session, "USD", start=start, end=end)
    assert (end - captured["start"]).days == fx_live.MAX_HISTORY_DAYS


def test_refresh_widens_cache_when_a_longer_range_is_later_requested(db_session, monkeypatch):
    """A previously-cached short range must not be silently returned
    truncated when a later, wider range is requested."""
    calls: list[tuple[date, date]] = []

    def _fake_fetch(base, quotes, start, end):
        calls.append((start, end))
        return {d: {q: Decimal("1.0") for q in quotes} for d in (start, end)}

    monkeypatch.setattr(fx_live, "fetch_series", _fake_fetch)

    today = date(2026, 7, 6)
    fx_live.refresh(db_session, "USD", start=today - timedelta(days=2), end=today)
    assert len(calls) == 1

    result = fx_live.refresh(db_session, "USD", start=today - timedelta(days=60), end=today)
    assert len(calls) == 2  # re-fetched instead of reusing the narrower cache
    assert result.series[0]["date"] <= today - timedelta(days=60)
