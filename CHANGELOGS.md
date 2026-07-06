# Changelog

All notable changes to Loaf & Ledger are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-06

A bug-fix, budgeting-rework, and restyle pass on top of the initial slice. Backward
compatible with 0.0.0's API contracts.

### Added
- **Live FX rates:** `services/fx_live.py` now fetches from Frankfurter (ECB reference
  rates) over an explicit date range (`/fx/rates?start=&end=`), caching a daily history and
  falling back to cached data offline. Capped at 365 days per request.
- **Budget periods + initial fund (F4):** `/budgets/status` now accepts `scope`
  (month/3m/ytd/all) + `anchor` in addition to the legacy `year`+`month`, aggregating
  limits and spend across however many calendar months the scope covers. New
  `/budgets/fund` (GET/POST/DELETE) tracks a period's "initial fund," defaulting to the
  prior period's ending running balance (carried over automatically) and overridable per
  user. New `fund_overrides` table + migration.
- **Monthly-by-category analytics:** `/analytics/monthly-by-category` feeds a new stacked
  expense-mix chart on the Analytics page.
- **Ledger inline edit:** the frontend now uses the previously-unused
  `PATCH /ledger/transactions/{id}` endpoint — edit category, amount, currency, date/time,
  and note in place (direction is still not editable). The transaction list also scrolls
  within its own panel instead of growing the page indefinitely.
- **Hover tabs:** a new reusable tab-strip component that switches panels on hover and
  pins on click, used to split the Analytics page (Overview/Trends/Categories) and the
  reworked Budgets page (By category/Trend).
- **Combo + stacked charts:** the Analytics monthly chart now overlays a net-cashflow line
  on the income/expense bars; a new stacked bar chart shows the expense-category mix over
  time.
- **Dashboard highlight card:** the Balance card gets a bold, filled treatment — the one
  emphasized card on the Dashboard, distinct from the plain cards elsewhere.
- **More insights:** three new rule-based insights (diversified spend, multiple income
  streams, no expenses yet this period).
- **Tests:** budget-period date math, multi-month budget aggregation + currency
  conversion, the fund-override lifecycle, monthly-by-category aggregation, FX range/cache
  behavior, and ledger-edit coverage (58 tests total, up from 23).

### Changed
- **Theme:** "Ledger & Crust" now runs crust-brown as the primary/structural color (buttons,
  segmented controls, active nav) instead of green; green is kept for its credit/financial
  meaning only. Paper and card backgrounds warmed toward flour/crumb tones, plus a small
  wheat-sprig accent on the brand mark.
- **Dashboard FX chart:** redesigned from a single percent-normalized line chart into
  small-multiple charts, one per currency, each showing real nominal values with the
  day-over-day change surfaced on hover instead of baked into the plotted value.
- **Budgets page:** replaced the free-form month/year picker with a Month/3M/YTD/All period
  selector (page-local, independent of the global time-range filter); the running-balance
  chart and KPIs now consistently follow that same local period instead of mixing local and
  global scopes.
- **Monthly chart + FX chart range-awareness:** both now scale with the selected global
  time range instead of a hardcoded 6 months / 7 days.

### Fixed
- **Date-range/timezone bug:** `rangeBounds()`/`previousRangeBounds()` (and the ledger's
  "new entry" date default) built date-only strings via `Date#toISOString()`, which
  renders in UTC and silently shifted "this month"/"YTD"/etc. boundaries by a day for
  timezones ahead of UTC (e.g. the Philippines, UTC+8) — this is why charts and ledger
  filters could look misaligned with the selected date scope. Fixed by formatting from
  local date components instead.
- **FX cache coverage:** `fx_live.refresh()` previously judged its cache "fresh enough"
  based only on the newest cached point's age, which could silently return a truncated
  series if a wider range was requested after a narrower one had already been cached. It
  now also checks that the cache reaches back far enough to cover the requested start.
- A route-ordering bug in `/budgets` that would have shadowed `DELETE /budgets/fund` behind
  the pre-existing `DELETE /budgets/{budget_id}` catch-all.

## [0.0.0] — 2026-07-06

Initial architecture spike and first working slice. Everything below lands together
as the inaugural cut.

### Added
- **Regional salary engine (F1):** strategy-pattern tax engine with national rule sets
  for the Philippines, United States (federal), Australia, and the EU (modelled via
  Germany). Live calculator plus persistent, snapshotted salary profiles.
- **Ledger (F2):** categorized inbound/outbound transactions with a two-tier taxonomy
  (system-seeded + user custom) and a `statutory` flag separating mandatory deductions
  from discretionary spend.
- **Cross-metric analytics (F3):** income/expense aggregation, savings rate, salary
  deduction rate, per-category breakdown, and a six-month income-vs-expense series.
- **Budget tracker (F4):** per-category monthly limits with spent/remaining/utilization
  status and over-budget flagging.
- **CSV export (F5):** server-streamed expense export with an optional converted-amount
  column.
- **Dashboard (F6):** balance-sheet summary honoring global filters (time range, region,
  display currency) plus rule-based insights.
- **Currency:** display-only conversion over a static, seeded exchange-rate table
  (amounts stored natively).
- **Platform:** FastAPI + SQLAlchemy 2.0 backend (SQLite for dev, PostgreSQL for prod via
  a JSONB variant), Alembic migrations, idempotent seed script, and a Vite + React + TS
  frontend using TanStack Query and Zustand.
- **Tests:** pytest unit suite for the tax engine and integration suite for the API
  (23 tests).

### Notes
- Tax figures are planning-grade approximations of national statutory rules, not
  tax-filing advice.
- Deployment target is a local, single-user, self-hosted instance (no multi-user auth).

[0.1.0]: https://github.com/RCEjosephkarl/Loaf-and-Ledger/releases/tag/v0.1.0
[0.0.0]: https://github.com/RCEjosephkarl/Loaf-and-Ledger/releases/tag/v0.0.0
