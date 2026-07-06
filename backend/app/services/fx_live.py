"""Live FX rates from Frankfurter (ECB reference rates, free, no API key).

This is the one place in the app that reaches the network. A refresh updates
the "current" `exchange_rates` table used by `services/currency.convert()`
everywhere else, and caches a short daily history in `exchange_rate_history`
for the dashboard trend chart and CSV export. Any network failure falls back
to whatever is already cached — the app must keep working offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models.base import REGION_CURRENCY
from app.models.fx import ExchangeRate, ExchangeRateHistory

FRANKFURTER = "https://api.frankfurter.dev/v1"
HISTORY_DAYS = 7
# Cap for caller-supplied ranges (e.g. the "All" time scope) — daily
# granularity, one round trip, keeps us polite to the free upstream API.
MAX_HISTORY_DAYS = 365
TIMEOUT = 5.0


def fetch_series(
    base: str, quotes: list[str], start: date, end: date
) -> dict[date, dict[str, Decimal]] | None:
    """Fetch a daily close-rate time series. Returns None on any failure."""
    if not quotes:
        return {}
    try:
        resp = httpx.get(
            f"{FRANKFURTER}/{start.isoformat()}..{end.isoformat()}",
            params={"from": base, "to": ",".join(quotes)},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        return {
            date.fromisoformat(d): {k: Decimal(str(v)) for k, v in rates.items()}
            for d, rates in payload["rates"].items()
        }
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


@dataclass
class RefreshResult:
    base: str
    quotes: list[str]
    live: bool
    as_of: date | None
    series: list[dict]  # [{"date": date, "rates": {quote: Decimal}}], oldest -> newest


def _cached_series(
    db: Session, base: str, quotes: list[str], since: date, until: date
) -> list[dict]:
    rows = (
        db.execute(
            select(ExchangeRateHistory)
            .where(
                ExchangeRateHistory.base_currency == base,
                ExchangeRateHistory.quote_currency.in_(quotes),
                ExchangeRateHistory.as_of >= since,
                ExchangeRateHistory.as_of <= until,
            )
            .order_by(ExchangeRateHistory.as_of)
        )
        .scalars()
        .all()
    )
    by_date: dict[date, dict[str, Decimal]] = {}
    for r in rows:
        by_date.setdefault(r.as_of, {})[r.quote_currency] = Decimal(str(r.rate))
    return [{"date": d, "rates": rates} for d, rates in sorted(by_date.items())]


def _upsert_history(db: Session, base: str, quote: str, as_of: date, rate: Decimal) -> None:
    existing = db.execute(
        select(ExchangeRateHistory).where(
            ExchangeRateHistory.base_currency == base,
            ExchangeRateHistory.quote_currency == quote,
            ExchangeRateHistory.as_of == as_of,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.rate = rate
    else:
        db.add(
            ExchangeRateHistory(base_currency=base, quote_currency=quote, rate=rate, as_of=as_of)
        )


def _upsert_current(db: Session, base: str, quote: str, rate: Decimal, as_of: date) -> None:
    existing = db.execute(
        select(ExchangeRate).where(
            ExchangeRate.base_currency == base, ExchangeRate.quote_currency == quote
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.as_of <= as_of:
            existing.rate = rate
            existing.as_of = as_of
    else:
        db.add(ExchangeRate(base_currency=base, quote_currency=quote, rate=rate, as_of=as_of))


def refresh(
    db: Session, base: str, *, start: date | None = None, end: date | None = None
) -> RefreshResult:
    """Refresh + return base->quote close rates for [start, end] (inclusive).

    Defaults to the last HISTORY_DAYS when no range is given (unchanged
    behavior for existing callers). Skips the network call when the cache
    already covers the requested range with a recent-enough newest point (FX
    closes don't change intraday, and don't publish on weekends), and falls
    back to whatever is cached if the external API is unreachable.
    """
    base = base.upper()
    quotes = sorted({c for c in REGION_CURRENCY.values() if c != base})
    end = end or date.today()
    if start is None:
        start = end - timedelta(days=HISTORY_DAYS - 1)
    elif (end - start).days > MAX_HISTORY_DAYS:
        start = end - timedelta(days=MAX_HISTORY_DAYS)

    newest_cached = db.execute(
        select(ExchangeRateHistory.as_of)
        .where(ExchangeRateHistory.base_currency == base)
        .order_by(ExchangeRateHistory.as_of.desc())
        .limit(1)
    ).scalar_one_or_none()
    oldest_cached = db.execute(
        select(func.min(ExchangeRateHistory.as_of)).where(
            ExchangeRateHistory.base_currency == base
        )
    ).scalar_one_or_none()

    # The cache must both be recent *and* reach back far enough to cover the
    # requested start — otherwise a later, wider request (e.g. "All" after an
    # earlier "This month") would silently return a truncated series.
    covers_range = oldest_cached is not None and oldest_cached <= start
    fresh_enough = (
        newest_cached is not None and (end - newest_cached).days <= 1 and covers_range
    )
    live = fresh_enough

    if not fresh_enough:
        fetched = fetch_series(base, quotes, start, end)
        if fetched:
            live = True
            for as_of, rates in fetched.items():
                for quote, rate in rates.items():
                    _upsert_history(db, base, quote, as_of, rate)
            # Update the "current" table once per quote, from the latest date only —
            # calling this per-date (with autoflush disabled) would queue multiple
            # pending inserts for the same (base, quote) pair and collide on commit.
            latest_date = max(fetched)
            for quote, rate in fetched[latest_date].items():
                _upsert_current(db, base, quote, rate, latest_date)
            db.commit()

    series = _cached_series(db, base, quotes, start, end)
    as_of = series[-1]["date"] if series else None
    return RefreshResult(base=base, quotes=quotes, live=live, as_of=as_of, series=series)
