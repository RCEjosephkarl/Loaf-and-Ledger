# Changelog

All notable changes to Loaf & Ledger are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/).

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

[0.0.0]: https://github.com/RCEjosephkarl/Loaf-and-Ledger/releases/tag/v0.0.0
