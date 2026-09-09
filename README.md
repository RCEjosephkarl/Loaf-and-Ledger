# Loaf & Ledger

*A personal-finance application that keeps a salaried breadwinner's money in a real
double-entry ledger, mirrors it into a star-schema warehouse, and tells the story back
in plain language.*

**Release:** `v0.2.0` (2026-09-09) · **Target:** Local, self-hosted, single-user, PHP (`₱`) only

---

## Abstract

Most budgeting apps store money as a flat list of categorized rows, which quietly makes
two things impossible: proving the books are internally consistent, and separating *moving*
money from *spending* it. Loaf & Ledger is built for the Filipino salaried worker who wants
to reason about **gross-to-net under PH statutory rules** while keeping a ledger that is
actually a ledger.

It runs **two databases on purpose**:
1. The write side is a normalized, constraint-enforced **double-entry journal** (OLTP)
   where every entry's debits equal its credits.
2. The read side is a physically separate **DuckDB star schema** (OLAP), kept in step
   via **write-through ETL** so analytics are never stale, and rebuildable from the journal
   at any time.

A strategy-pattern **tax engine** computes statutory payroll deductions under Philippine
TRAIN law. Payslips post directly into the ledger as balanced multi-line entries — gross
credited to income, withholdings debited to statutory accounts, and the remainder banked —
uniting payroll planning and bookkeeping into a single coherent system.

This document details the problem, the design decisions, the two-database architecture,
the feature set across all six application sections, and how to run and verify the system.

---

## 1. Motivation

A salaried worker's central financial question is deceptively simple: *of what I earn, how
much do I actually keep, and where does the rest go?* Answering it well requires four
foundations that existing personal-finance tools rarely combine:

1. **Accurate statutory payroll math.** Net pay under the Philippine TRAIN law is gross
   less mandatory contributions (SSS, PhilHealth, Pag-IBIG) and progressive income tax.
   Statutory contributions are themselves deductible before tax brackets apply.
2. **Books that can be proved.** When debits and credits must balance on every journal
   entry, the application can produce a trial balance that ties. A flat table of rows
   can only be trusted on faith.
3. **A model that knows moving money from spending it.** Transferring ₱5,000 from a payroll
   account into a savings account or GCash wallet is not an expense. In a single-entry schema
   with a "Savings" category it is — and your savings rate is then wrong by construction.
   *(This app previously had that exact flaw in v0.1.0; double-entry bookkeeping permanently
   fixed it).*
4. **Insight that a person can trust.** A number is more useful when the app can say, in
   plain words, *why it matters* — using transparent, deterministic rules rather than
   an opaque black box.

Loaf & Ledger addresses all four, deliberately scoped to a **local, single-user, self-hosted,
single-currency (PHP)** environment.

---

## 2. Design decisions

Every decision was evaluated against concrete alternatives to satisfy the requirements
recorded in [`CHANGELOGS.md`](./CHANGELOGS.md):

| Area | Decision | Why |
|------|----------|-----|
| **Repo** | Monorepo: `backend/` + `frontend/` | Atomic cross-stack changes for a solo build; JS workspaces add needless complexity across a Python backend. |
| **Write model** | **Double-entry journal** — balanced debit/credit lines against a PH chart of accounts | Makes the books provable: trial balances tie, and internal transfers between assets/liabilities are structurally distinct from spending. A payslip becomes *one* multi-line journal entry instead of disconnected rows. |
| **The balance invariant** | Enforced in one service (`services/journal.py`), re-checked by `integrity_check()` | `SUM(debit) = SUM(credit)` spans rows across lines, which standard portable SQL table CHECK constraints cannot enforce. One writer owns it; per-line CHECKs cover single-row constraints (non-negative, single-sided, non-zero). |
| **Read model** | Dedicated **DuckDB star schema** (`warehouse.duckdb`), never OLTP tables | The stores have distinct workloads: OLTP handles atomic ACID entries; OLAP answers multi-month multidimensional aggregations in a single columnar scan without Python loop overhead. |
| **Store synchronization** | **Write-through ETL** on every mutation, plus in-process & CLI rebuild | New ledger entries are queryable in analytics before the HTTP response returns — zero refresh lag. On warehouse failure, the store marks itself stale and reports drift via `/warehouse/status` without failing the ledger write (OLTP is system of record). |
| **Tax engine** | Strategy interface (`TaxRule`) + versioned data | Bracket logic lives in expressive, tested code; bracket thresholds live in versionable configuration. v0.2.0 implements the Philippines (TRAIN), while the registry architecture keeps new regimes modular. |
| **Currency** | **PHP only** — no stored currency columns | Storing multiple currencies and converting on every read created a hot-path performance tax for a domestic user. A single constant (`models.base.CURRENCY`) marks the extension seam. |
| **Timestamps** | Single non-null `occurred_at` datetime | Collapsed legacy `occurred_on` date and nullable `occurred_time` into a single UTC datetime, eliminating `time or time.min` coalesce hacks and timezone drift across date boundaries. |
| **Deletes & Auditability** | **Soft deletes**: entries voided, accounts archived | Erasing historical ledger rows destroys auditability. Accounts with historical postings are archived (`archived_at`) rather than dropped, preserving historical journal lines. |
| **Color & Accessibility** | CVD-validated 8-slot categorical palette | Validated with colour-vision deficiency simulation on both light and dark themes (CVD dE 9.1 light / 8.4 dark; normal vision dE 19.6 / 19.3). Semantic financial roles (credit, debit, good, warn) are reserved and never cycled into series colors. |
| **Auth** | None (single implicit user) | Scoped as a personal, local, self-hosted tool. User models retain foreign-key relationships to support an app-password seam without schema overhaul. |
| **Insights** | Deterministic rule-based heuristics | Transparent, explainable, and verifiable by hand. No external AI dependencies or statistical black boxes for financial advice. |
| **Frontend state** | TanStack Query (server state) + Zustand (global filters) | Read-heavy and cache-friendly. A single Zustand store manages time-range, account filter, and theme, cascading automatically to all query hooks. |
| **Datastores** | SQLite (dev) / PostgreSQL (prod) for OLTP; DuckDB for OLAP | Zero-configuration local startup with SQLite; production keeps indexable JSONB via SQLAlchemy type variants. `DATABASE_URL` and `WAREHOUSE_PATH` configure each datastore independently. |

---

## 3. Architecture

Two stores, two jobs. The write-through ETL arrow between them forms the backbone of the system.

```
        ┌───────────────────── frontend/ (Vite + React + TS) ─────────────────────┐
        │  Zustand { timeRange, accountId, theme } ─ cascades to every read        │
        │  TanStack Query hooks ───────────────▶  /api/v1/*                        │
        └────────────────────────────────────┬────────────────────────────────────┘
                                             │ (Vite dev proxy)
        ┌────────────────────────────────────▼───────────────── backend/ (FastAPI) ┐
        │                                                                          │
        │   WRITE PATH                              READ PATH                      │
        │   ──────────                              ─────────                      │
        │   routers/{accounts,payees,ledger,        routers/{analytics,dashboard,   │
        │            salary,budgets}                         budgets}              │
        │        │                                       │                         │
        │        ▼                                       ▼                         │
        │   services/journal.py  ← the balance      warehouse/queries.py           │
        │        │  invariant lives here                 │                         │
        │        ▼                                       │                         │
        │   ┌──────────────────┐   write-through   ┌─────▼──────────────────┐      │
        │   │  OLTP (SQLite /  │──── ETL, in the ──▶│  OLAP (DuckDB)         │      │
        │   │  PostgreSQL)     │     same request   │  warehouse.duckdb      │      │
        │   │                  │                    │                        │      │
        │   │ accounts         │◀─── rebuild_all ───│ dim_date · dim_account │      │
        │   │ payees           │     (CLI or POST)  │ dim_payee · dim_source │      │
        │   │ journal_entries  │                    │ fact_ledger_line       │      │
        │   │ journal_lines    │                    │ fact_payslip_item      │      │
        │   │ budgets · salary │                    │ agg_monthly_account    │      │
        │   │                  │                    │ agg_daily_cashflow     │      │
        │   │ SYSTEM OF RECORD │                    │ DERIVED — safe to drop │      │
        │   └──────────────────┘                    └────────────────────────┘      │
        └──────────────────────────────────────────────────────────────────────────┘
              Alembic migrations                        DDL applied on connect
```

### Write-through ETL vs. Batch Jobs

A batch-scheduled warehouse creates data lag: a salary or expense just recorded would be missing
from analytics until the batch executes. Loaf & Ledger resolves this by invoking
`etl.apply_entry()` within the same request lifecycle as the ledger write:
- It upserts the entry's fact rows in `fact_ledger_line`.
- It recalculates the affected monthly account rollups (`agg_monthly_account`) and daily cashflows (`agg_daily_cashflow`).
- Edits, voids, and replays follow the same deterministic delete-and-reinsert path.

### Resilience and Failure Isolation

OLTP is the system of record. Warehouse write operations are wrapped in safe exception handling:
if DuckDB writes fail (e.g. temporary file lock), the error is logged, the warehouse is flagged as
`stale`, and the ledger transaction completes successfully.
- `GET /warehouse/status` compares OLTP line counts against OLAP fact counts, reporting drift and running invariant checks.
- When drift is detected, the UI displays an actionable **Rebuild warehouse** banner.
- `POST /warehouse/rebuild` executes a full reload in-process without server downtime.
- CLI reload (`python -m app.warehouse.rebuild`) is available for offline batch rebuilding.

### Warehouse Star Schema & Grain

The DuckDB OLAP warehouse models financial history across four dimensions, two facts, and two aggregate rollups:

| Table | Type | Role & Grain |
|---|---|---|
| `dim_date` | Dimension | Calendar day dimension (date, year, month, quarter, day of week, month label). |
| `dim_account` | Dimension | Denormalized chart of accounts (code, name, type, flow class, statutory flag). |
| `dim_payee` | Dimension | Payees (name, active status). |
| `dim_source` | Dimension | Entry provenance (`manual`, `salary`, `opening`, `transfer`) — static, preserved across rebuilds. |
| `fact_ledger_line` | Fact | Atomic fact: **one journal line**. Stores signed amounts, debit/credit flags, and `is_transfer`. |
| `fact_payslip_item` | Fact | One line-item of a saved statutory salary breakdown. Powers the gross-to-net waterfall. |
| `agg_monthly_account` | Rollup | Monthly inflow and outflow totals per account. Feeds stacked expense mix charts. |
| `agg_daily_cashflow` | Rollup | Daily inflows, outflows, net change, and cumulative running cash balance. |

> **The `is_transfer` flag:** During fact loading, an entry is classified as a transfer (`is_transfer = true`)
> if all lines hit balance-sheet accounts (assets, liabilities, equity). Analytical queries for income and
> expense automatically filter these out. This ensures moving ₱10,000 from a checking account to GCash
> or high-yield savings never inflates income or expenses.

### Feature → Endpoint Map

| Module | Endpoints | Description |
|---|---|---|
| **Accounts** | `GET /accounts`<br>`POST /accounts`<br>`PATCH /accounts/{id}`<br>`DELETE /accounts/{id}`<br>`GET /accounts/balances` | Chart of accounts CRUD, soft archiving (`DELETE`), and point-in-time normal balance aggregation. |
| **Payees** | `GET /payees`<br>`POST /payees` | Payee directory for transaction tagging. |
| **F1 Salary** | `POST /salary/calculate`<br>`GET /salary/profiles`<br>`POST /salary/profiles`<br>`PATCH /salary/profiles/{id}`<br>`DELETE /salary/profiles/{id}`<br>**`POST /salary/profiles/{id}/post`** | Gross-to-net tax calculation, profile management, and **one-click idempotent payslip posting** to the journal. |
| **F2 Ledger** | `GET /ledger/entries`<br>`POST /ledger/entries`<br>`GET /ledger/entries/{id}`<br>`PATCH /ledger/entries/{id}`<br>`DELETE /ledger/entries/{id}`<br>`POST /ledger/entries/simple` | Complete journal CRUD, soft-voiding (`DELETE`), and two-line quick entry posting. |
| **F3 Analytics** | `GET /analytics/overview`<br>`GET /analytics/monthly`<br>`GET /analytics/monthly-by-account`<br>`GET /analytics/running-balance`<br>`GET /analytics/earnings` | DuckDB OLAP queries: multi-act financial summary, stacked mix, cashflow series, and waterfall items. |
| **F4 Budgets** | `GET /budgets`<br>`POST /budgets`<br>`PATCH /budgets/{id}`<br>`DELETE /budgets/{id}`<br>`GET /budgets/status`<br>`GET /budgets/fund`<br>`POST /budgets/fund`<br>`DELETE /budgets/fund` | Expense account budget limits, multi-month period status, and period initial fund tracking with carryover. |
| **F5 Export** | `GET /export/ledger.csv`<br>`GET /export/trial-balance.csv` | Streamed CSVs: granular journal lines (`ledger.csv`) and verified debit/credit balance proofs (`trial-balance.csv`). |
| **F6 Dashboard** | `GET /dashboard/summary` | Balance sheet highlight summary, top expense accounts, and deterministic insights. |
| **Warehouse** | `GET /warehouse/status`<br>`POST /warehouse/rebuild` | OLTP-to-OLAP drift checking, integrity verification, and in-process warehouse truncation and reload. |
| **Meta & User** | `GET /meta`<br>`GET /user`<br>`PATCH /user` | Instance configuration, modelled jurisdiction metadata, and user preferences. |

---

## 4. Method: the tax engine & payslip posting

The tax engine (`app/tax/`) implements a strategy interface:
```python
compute_annual(gross: Decimal, year: int) -> Breakdown
```
The Philippine regime (`app/tax/regions/ph.py`) encodes TRAIN law brackets, SSS contribution tables,
PhilHealth percentage deductions, and Pag-IBIG statutory caps:

```
compute(gross, pay_period) ─▶ annualize ─▶ PH TRAIN rule ─▶ Breakdown ─▶ post_payslip() ─▶ journal
       Breakdown = { gross, statutory line items, net, totals, effective_rate }
```

### Statutory Payroll Invariants

1. **Mandatory contributions precede income tax:** SSS, PhilHealth, and Pag-IBIG are computed
   first and subtracted from gross income before progressive income tax brackets apply.
2. **Floor effects:** Below statutory contribution floors, flat contribution minimums produce a
   **regressive effective deduction rate** — a real-world legal property explicitly verified by tests.
3. **Immutable snapshots:** Calculated breakdowns are stored on salary profiles as JSONB snapshots,
   protecting past payslip records against future tax code updates.

### Balanced Multi-Line Payslip Posting

When a user posts a payslip (`POST /salary/profiles/{id}/post`), `services/payslip.py` turns the snapshot
into a balanced multi-line journal entry:

```
DR 6020 SSS                    1,350.00   (Statutory liability/expense)
DR 6030 PhilHealth             1,050.00   (Statutory liability/expense)
DR 6040 Pag-IBIG                 100.00   (Statutory liability/expense)
DR 6010 Income tax (BIR)       3,108.33   (Statutory liability/expense)
DR 1020 Bank — payroll        36,391.67   (Asset account receiving net pay)
                CR 4010 Base salary               42,000.00   (Gross income account)
─────────────────────────────────────────────────────────────────────────────
Total Debits: ₱42,000.00  |  Total Credits: ₱42,000.00  (✓ Balanced)
```

Posting is strictly **idempotent**: backed by a unique database constraint on `(user_id, source, source_ref)`,
preventing double-posting even if clicked repeatedly or retried over the network.

---

## 5. Results: what the app does

Loaf & Ledger delivers six cohesive, end-to-end modules styled with the *"Ledger & Crust"* design system:
warm crust-brown structural accents, flour/crumb card backgrounds, faint greenbar tabular row striping,
monospaced financial tables, and the accountant's double underline for net balances.

Contextual **`InfoNote` popovers** replace bulky explanatory paragraphs throughout the UI, keeping
screens clean and figures above the fold while remaining accessible via hover, click/pin, and keyboard navigation.

### 01 · Dashboard — "Where the dough goes"
- **Crust Highlight Card:** The central balance sheet summary card displaying Credits in, Debits out,
  and Net cashflow with double-underline emphasis, accompanied by net worth and transfer volume.
- **Transfers Highlight:** Explicitly surfaces money *"moved rather than spent"*, making saving visible.
- **Plain-Language Insights:** Deterministic heuristics highlighting spending velocity, runway,
  statutory deduction load, and spending concentration.
- **Trends:** Balance over time line chart and monthly income/expense/net cashflow combo chart.
- **Top Outflows:** Ranked expense accounts for the selected time horizon.

### 02 · Salary — "What survives to net"
- **Interactive Calculator:** Enter gross pay (monthly or annual) to preview SSS, PhilHealth,
  Pag-IBIG, BIR withholding, net take-home, and effective deduction rates.
- **Profile Snapshots:** Save configurations as persistent profiles for instant reference.
- **One-Click Ledger Posting:** Designate an asset account (e.g. Payroll Bank) and post the payslip
  directly into the journal as a balanced 6-line entry with full idempotency guards.

### 03 · Accounts — "Every pocket, named"
- **Chart of Accounts:** Grouped into Assets (1xxx), Liabilities (2xxx), Equity (3xxx), Income (4xxx),
  Expenses (5xxx), and Statutory Deductions (6xxx).
- **Derived Real-Time Balances:** Every balance is calculated dynamically from journal lines according
  to normal-balance conventions (assets/expenses debit-normal; liabilities/equity/income credit-normal).
- **Safe Archiving:** Accounts with historical postings cannot be hard-deleted; archiving them
  hides them from active pickers while preserving historical audit trails.
- **Trial Balance CSV:** Download a standard two-column trial balance (`/export/trial-balance.csv`)
  where total debits and credits mathematically tie.

### 04 · Ledger — "Every entry, dated and dressed"
- **Two-Line Quick Form:** Fast logging for standard transactions (**Money out**, **Money in**, **Transfer**)
  between two accounts, with automatic dual-line posting.
- **Advanced Journal Grid:** Specialized interface for multi-line transactions (>2 lines: split bills,
  part-payments, manual payroll) with a live debits-vs-credits balance meter that gates submission
  until `SUM(debits) = SUM(credits)`.
- **Full Historical Running Balance:** A continuous cash balance column spanning the entire ledger
  history rather than artificially resetting at window boundaries.
- **Soft Voiding:** Voiding an entry preserves the row with visual strikethrough and void badge.
- **Ledger Export:** Stream the entire journal as CSV (`/export/ledger.csv`) at one row per journal line.

### 05 · Budgets — "Limits, and how close you are"
- **Category Limits:** Set monthly limits across expense accounts with progress tracks that shift
  from green to amber to red when exceeding 100% utilization.
- **Flexible Scopes:** Switch between Month, 3 Months, YTD, and All period scopes.
- **Initial Fund Tracking:** Tracks starting balance for a period, defaulting to prior cumulative
  cashflow with user override capability (`/budgets/fund`).
- **Warehouse-Backed:** Budget spend queries DuckDB directly, ensuring zero discrepancy with Analytics.

### 06 · Analytics — "The story your money tells"
The flagship feature, structured as a **four-act narrative** with sticky left-hand navigation,
smooth scrolling, and prose-led ledes featuring live data figures:

| Act | Central Question | Visual & Analytical Evidence |
|---|---|---|
| **I · What came in** | *"Every payday ₱X is earned and ₱Y reaches your account — Z% of gross."* | **Gross-to-net waterfall chart** (`WaterfallChart`) built from `fact_payslip_item`. Deductions hang from where the last ended, largest bite first. Accompanied by ranked income sources. |
| **II · Where it went** | *"₱X went out. Category Y took Z%, and ₱W was never discretionary at all."* | Ranked horizontal expense bars with delta against prior period of equal duration. Stacked bar chart showing monthly expense mix by account. Transfers excluded. |
| **III · What's left** | *"You are ₱X ahead. At ₱Y/day, your cash covers Z more days."* | Cumulative cashflow chart, daily/weekly/monthly burn rates, and projected cash runway. |
| **IV · What it means** | *"Of everything that came in, you still hold X%."* | Account- and transfer-aware deterministic insights, paired with a complete summary figures table. |

- **Real-Time Warehouse Monitor:** An alert banner appears if OLAP fact drift is detected, offering
  a one-click in-process **Rebuild warehouse** button.

### Design System & Color Accessibility
- **The "Ledger & Crust" Aesthetic:** A tactile aesthetic balancing baker's warmth and accountant's rigor.
  Structural primary color is crust brown; card backgrounds use flour and crumb tones; money tables feature
  monospace tabular numerals, faint greenbar alternating row striping, and the classic double underline for totals.
- **CVD-Validated 8-Slot Palette:** Categorical chart hues are assigned in a fixed order and never cycled;
  a ninth category folds into "Other". Palette contrast was validated with colour-vision deficiency simulations
  against the application's actual chart surfaces across both light and dark themes (light: CVD $\Delta E$ 9.1,
  normal vision 19.6; dark: CVD $\Delta E$ 8.4, normal vision 19.3). Semantic financial roles (credit, debit,
  good, warn) are strictly reserved and never reassigned as series hues (see `frontend/src/lib/chartColors.ts`).
- **Contextual `InfoNote` Popovers:** Context and architectural explanations are preserved behind accessible
  infonote tooltips (hover, click-to-pin, and keyboard focusable), keeping screens tidy while retaining depth.

---

## 6. Evaluation

The test suite validates financial correctness, data integrity across both databases,
and user flows:

- **Unit Tests (`tests/unit/`):**
  - `test_journal.py`: Invariant validation (unbalanced, single-line, zero-amount, and two-sided lines rejected; `simple_entry` generates correct opposing lines; soft voiding).
  - `test_balances.py`: Normal-balance arithmetic per account type, trial balance equality, and proof that demo data never overdraws asset accounts.
  - `test_payslip.py`: Payslip posting balance, correct statutory account mapping, and idempotent re-posting prevention.
  - `test_tax_engine.py`: TRAIN progressive tax formulas against hand-verified figures, floor contribution edge cases, and the regressive effective deduction rate property.
  - `test_budget_periods.py`: Calendar period math, date boundary clamping, and year-rollover transitions.
- **Integration Tests (`tests/integration/`):**
  - `test_warehouse_sync.py`: Verifies real-time write-through ETL: posting an entry via the API immediately updates `fact_ledger_line`, rollups, and `/analytics/overview` with **zero manual refresh**. Also covers edits, voids, and cross-month boundary moves.
  - `test_warehouse_rebuild.py`: Proves full warehouse truncate-and-reload reproduces write-through data row-for-row.
  - `test_transfers.py`: Confirms internal transfers alter account balances without impacting expense totals or distorting savings rates.
  - `test_seed_cli.py`: Verifies that CLI tools detect DuckDB file locks cleanly when the API server is active and output clear remediation guidance.
  - `test_api.py`: Validates API endpoints and pins down the window-bounded savings rate calculation.
- **End-to-End & Static Analysis:** Headless SPA verification across light and dark themes, strict TypeScript compilation, and zero lint warnings.

```bash
# Run the test suite (105 tests passing)
cd backend && uv run pytest        # or: ./.venv/bin/pytest

# Lint backend code
cd backend && uv run ruff check .  # or: ./.venv/bin/ruff check .

# Validate frontend types and build production bundle
cd frontend && npm run build
```

---

## 7. Limitations & roadmap

- **Single currency.** PHP is assumed throughout; amounts carry no currency columns. The seam is
  `models.base.CURRENCY`. Multi-currency support would require intentional architecture for conversion points.
- **Single jurisdiction.** Philippines TRAIN rules only. The `TaxRule` registry enables new national
  regimes as modular plugins in `app/tax/regions/`.
- **DuckDB single-writer lock.** DuckDB permits one writer process per file. Running `uvicorn` holds
  the file lock, meaning CLI seed and rebuild scripts will detect the lock, exit cleanly, and direct
  the user to `POST /warehouse/rebuild`.
- **Line replacement on edit.** Amending a journal entry deletes and reinserts its line set rather
  than writing an immutable reversing entry. The schema reserves `journal_entries.reverses_id` for
  a future append-only mode.
- **Window-bounded savings rate.** Savings rate is defined strictly as `(income - expense) / income`
  over the active filter window. Earlier designs compared one payslip against multi-month expenses,
  producing erroneous negative rates.
- **Single-user deployment.** Auth is omitted by design for local self-hosting.

---

## 8. Project layout

```
Loaf-and-Ledger/
├── backend/
│   ├── app/
│   │   ├── models/        accounts · payees · journal_entries · journal_lines · budgets · salary
│   │   ├── services/      journal (the balance invariant) · payslip · balances · insights
│   │   ├── warehouse/     engine · ddl · etl · queries · status · rebuild   (DuckDB OLAP)
│   │   ├── routers/       accounts · payees · ledger · salary · budgets · analytics · dashboard · export · warehouse · meta
│   │   ├── tax/           TaxRule registry + regions/ph.py
│   │   ├── config.py · db.py · deps.py · main.py · schemas.py · seed.py
│   ├── migrations/        Alembic migrations
│   └── tests/
│       ├── unit/          test_journal · test_balances · test_payslip · test_tax_engine · test_budget_periods
│       └── integration/   test_warehouse_sync · test_warehouse_rebuild · test_transfers · test_seed_cli · test_api
├── frontend/
│   ├── src/
│   │   ├── api/           client endpoints
│   │   ├── components/    Brand · FilterBar · HighlightCard · InfoNote · Layout · Money · WaterfallChart · Charts
│   │   ├── pages/         Dashboard · Salary · Accounts · Ledger · Budgets · Analytics
│   │   ├── store/         Zustand filter store (timeRange, accountId, theme)
│   │   └── lib/           CVD-validated chart colors & utilities
│   ├── package.json · tsconfig.json · vite.config.ts
├── README.md · WALKTHROUGH.md · CHANGELOGS.md
```

---

## 9. Getting started

### Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- [`uv`](https://github.com/astral-sh/uv) (recommended) or standard `pip`/`venv`

### Step 1: Initialize Backend & Database

```bash
cd backend

# Install dependencies
uv sync --extra dev

# Run Alembic migrations to build the OLTP schema
uv run alembic upgrade head

# Seed the PH chart of accounts, PHP demo entries, and initial warehouse load
uv run python -m app.seed

# Start the FastAPI server (serves http://localhost:8000)
uv run uvicorn app.main:app --reload
```

> **Note on Seeding:** Run `python -m app.seed` **before** starting uvicorn. Because DuckDB is
> single-writer, an active uvicorn process holds `warehouse.duckdb`. If the server is already running,
> the seed will commit the ledger half and instruct you to run:
> ```bash
> curl -X POST localhost:8000/api/v1/warehouse/rebuild
> ```
> which triggers an in-process reload without downtime.

### Step 2: Launch Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser. The frontend dev server proxies `/api/v1` calls
directly to the FastAPI backend.

For a guided operational tour of all workflows, see [`WALKTHROUGH.md`](./WALKTHROUGH.md).

---

*Loaf & Ledger is licensed for personal use. Tax computations are planning-grade estimates
and must not be relied upon as official tax-filing advice.*
