# Changelog

All notable changes to Loaf & Ledger are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-09-09

A structural pass: the write model becomes a real double-entry ledger, analytics move to a
separate OLAP warehouse kept in step by write-through ETL, and the app narrows to a single
currency. **Breaking:** the schema, the API surface, and the stored data are all replaced —
there is no migration path from 0.1.0, by design (`Reset the data` was the brief).

### Added
- **Double-entry OLTP.** New `accounts` (a PH chart of accounts), `payees`,
  `journal_entries` and `journal_lines`. Every entry's debits equal its credits; the
  invariant is enforced in `services/journal.py`, the only module permitted to write those
  tables, and re-checked by `integrity_check()`. Per-line CHECK constraints cover what SQL
  can express (non-negative, single-sided, non-zero), real indexes were added throughout,
  and SQLite foreign keys are now actually switched on (`PRAGMA foreign_keys=ON`).
- **DuckDB OLAP warehouse** (`app/warehouse/`) in its own file. Star schema: `dim_date`,
  `dim_account`, `dim_payee`, `dim_source`; facts `fact_ledger_line` (grain: one journal
  line) and `fact_payslip_item`; rollups `agg_monthly_account` and `agg_daily_cashflow`.
- **Write-through ETL.** Every ledger mutation loads the affected facts and refreshes the
  touched rollups before the response returns, so a new earning is visible in analytics
  with no refresh step. A warehouse failure marks the store stale rather than failing the
  ledger write; `GET /warehouse/status` reports drift and integrity, `POST
  /warehouse/rebuild` and `python -m app.warehouse.rebuild` do a full reload.
- **Payslip posting** (`POST /salary/profiles/{id}/post`): a saved breakdown becomes one
  balanced multi-line journal entry — gross credited to income, each statutory withholding
  debited, the remainder banked. Idempotent via a unique `(user, source, source_ref)`.
- **Accounts section** in the UI: the chart of accounts grouped by type with derived
  balances, net worth, and archive; plus `GET /export/trial-balance.csv`, whose two columns
  must tie.
- **Journal entry grid** on the Ledger page for entries with more than two lines, with a
  live debits-vs-credits meter that gates the submit button.
- **Analytics rebuilt as a four-act narrative** — what came in, where it went, what's left,
  what it means — with a sticky act-nav, prose-led ledes carrying the real figures, and a
  new gross-to-net `WaterfallChart`.

### Changed
- **Single currency (PHP).** Removed the US/AU/EU tax rules, `jurisdictions`,
  `exchange_rates`, `exchange_rate_history`, the Frankfurter client, `services/currency.py`,
  the `/fx` router and `fx-rates.csv`. No table carries a currency column any more; the seam
  is the constant `models.base.CURRENCY`.
- **`transactions` and `categories` are gone**, replaced by the journal and the chart of
  accounts. `/ledger/transactions` becomes `/ledger/entries`; `expenses.csv` becomes
  `ledger.csv`, at one row per journal *line*.
- **Analytics and the dashboard now read from DuckDB**, not from Python aggregation loops
  over every row. `services/analytics.py` was deleted; its insight rules moved to
  `services/insights.py` and gained account- and transfer-awareness. Budget spend also
  comes from the warehouse, so it cannot disagree with the ledger.
- **`occurred_on` + nullable `occurred_time` collapsed into one non-null `occurred_at`**,
  removing the `time or time.min` coalesce at every sort site.
- **Deletes are soft**: entries are voided and accounts archived, so history stays readable.
- **Global filters** lost currency and region and gained **account** — with a chart of
  accounts, "only what touched the GCash wallet" is the slice worth having.
- **Chart colors** now come from a fixed eight-slot categorical palette, validated for
  colour-vision deficiency against this app's own chart surface in both themes. Series
  colors are never cycled; a ninth folds into "Other".

### Fixed
- **Savings and investments no longer count as spending.** The old chart had a
  `Savings & investment` *expense* category, so money moved into savings was recorded as an
  outflow and the savings rate was wrong by construction. A transfer between two
  balance-sheet accounts is now structurally distinct, flagged `is_transfer` in the fact
  table and excluded from every income and expense figure — while being reported on its own
  terms so the act of saving is still visible.
- **Savings rate no longer mixes time periods.** It used the active payslip's
  net-per-period as the reference income against a whole-window expense, so over "All" it
  reported figures like **-326%**. It is now net over the same window's income.
- **Amending an entry** no longer collides on the `(entry_id, line_no)` unique index:
  the old lines are deleted and flushed before the replacements are inserted.
- **`dim_source` is no longer truncated on rebuild.** It is a static dimension that facts
  join to; emptying it silently zeroed every total that joined through it.
- **`python -m app.seed` no longer dies with a traceback when the API server is running.**
  The seed writes both stores, and DuckDB's single-writer lock meant the warehouse half
  failed after the ledger half had already committed — leaving a seeded database, an empty
  warehouse, and a stack trace. It now reports the ledger it did seed, explains the lock,
  points at `POST /warehouse/rebuild` (or stopping the server), and exits non-zero. Lock
  detection and the hint text are shared with the rebuild CLI so they cannot drift.
- **The demo ledger no longer overdraws an asset.** Wallet top-ups are derived from the
  spending pattern, so cash and e-wallet balances can never go negative — pinned by a test.

### Removed
- The multi-currency display switch, the FX trend card, and the salary
  profile-comparison chart (all meaningless with one currency and one jurisdiction).

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
