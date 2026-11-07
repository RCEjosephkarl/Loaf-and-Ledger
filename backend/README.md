# Loaf & Ledger — Backend

FastAPI + SQLAlchemy for the double-entry journal, with DuckDB for analytics.
See the [project overview](../README.md), [walkthrough](../WALKTHROUGH.md), and
[UI/UX testing guide](../docs/UI_UX_TESTING.md).

## Local startup

Run these commands **from `backend/`**. Default database paths are relative to the
working directory; running from the repository root can open a different SQLite file.

```bash
uv sync --extra dev            # install (Python 3.12)
uv run alembic upgrade head    # create/update schema, including fortnightly support
uv run uvicorn app.main:app --reload
```

The existing local database was reset on 2026-11-07 with 36 built-in accounts at zero
balance. For a new database, follow [clean database setup](../WALKTHROUGH.md#clean-database-setup)
before starting the API. `uv run python -m app.seed` is an **optional demo loader**:
it creates opening balances and sample financial data when the ledger is empty.

## Configuration

Settings come from environment variables or `.env` in the working directory.

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./loaf_ledger.db` | Source-of-truth journal database. Use `postgresql+psycopg://…` for PostgreSQL. |
| `WAREHOUSE_PATH` | `./warehouse.duckdb` | Derived analytics database, separate from the journal. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed frontend origin for CORS. |
| `API_PREFIX` | `/api/v1` | Prefix for all application routes. |
| `DEFAULT_TAX_YEAR` | `2025` | Existing Philippine tax-rule year used by salary calculations. |

## Migrations

Run `uv run alembic upgrade head` before using the current frontend with an existing
database. Head revision is `0002_fortnightly`. It preserves existing profile snapshots,
adds `FORTNIGHTLY` to the PostgreSQL enum, and widens the SQLite column to 11 characters.
Downgrade is refused while fortnightly profiles remain. See [migration notes](migrations/README).

## Warehouse operations

With the API running, use its existing connection:

```bash
curl -fsS http://localhost:8000/api/v1/warehouse/status
curl -fsS -X POST http://localhost:8000/api/v1/warehouse/rebuild
```

With the API stopped:

```bash
uv run python -m app.warehouse.rebuild
```

DuckDB allows one writer process per file. A separate seed/rebuild process cannot open
the warehouse while the API owns it. Rebuilding mirrors existing journal/profile data;
it does not reset the journal or restore demo entries.

## Current API behavior

- Dashboard, monthly analytics, and running balances accept explicit date bounds.
  Monthly `start`/`end` bounds override legacy `months` requests. With neither date
  bounds nor `months`, monthly requests return complete history and include empty
  calendar months. Explicit legacy `months` values accept 1–36.
- `/accounts/balances` returns selected-period debits/credits and all-history closing
  balances through `end`. Unfiltered and `as_of` timestamp requests remain supported.
- `/ledger/entries/page?page=1&page_size=10` returns `items`, `total`, `posted_total`,
  `page`, and `page_size`. Items include `cash_balance` across complete non-voided
  asset history, including archived accounts. `page_size` accepts 1–100.
- `/ledger/entries` retains its list response and optional filters, including
  `include_voided=true`. Default list limit is 500, with a maximum of 2,000;
  pagination is the route for browsing beyond that limit.
- Salary accepts `monthly`, `fortnightly` (26/year), and `annual` periods.
  `POST /salary/profiles/{id}/activate` selects a saved profile. Posting remains
  idempotent **per profile**, rather than per payday.
- Budgets APIs retain their explicit period scopes; the frontend always requests the
  current month.
- Normal UI deletion voids journal entries or archives eligible accounts. The clean
  test reset was a separate, backed-up maintenance operation.

## Validation

```bash
uv run pytest
uv run ruff check .
```

Tests use temporary SQLite and DuckDB databases, separate from the working data.
The 2026-11-07 validation passed 121 backend tests. SQLite migration execution and
PostgreSQL SQL generation were checked; PostgreSQL migration execution remains unverified.
The frontend was also type-checked, built, and exercised in desktop/mobile browsers.
