# Loaf & Ledger

*A personal-finance application that treats a salaried breadwinner's money like a
double-entry ledger — with regional payroll rules baked in and plain-language insight
laid on top.*

---

## Abstract

Most budgeting apps assume one country's payroll rules and one currency. Loaf & Ledger is
built for the person who wants to reason about **gross-to-net across regimes** — the
Philippines, the United States, Australia, and the EU — while keeping a categorized ledger
of everything that flows in and out. It pairs a strategy-pattern **tax engine** with a
transactional ledger and derives **rule-based, transparent insights** from the two. This
document explains the problem, the design decisions and why each was made, the
architecture, and how to run and verify the system.

---

## 1. Motivation

A salaried worker's central financial question is deceptively simple: *of what I earn, how
much do I actually keep, and where does the rest go?* Answering it well requires three
things existing tools rarely combine:

1. **Accurate, region-specific payroll math.** "Net pay" means different things under PH
   TRAIN brackets, US federal + FICA, Australian PAYG + Medicare levy, or German
   income-tax-plus-social-insurance.
2. **A ledger that separates payroll from behavior.** Mandatory deductions and
   discretionary spending are different questions; conflating them poisons any analysis.
3. **Insight that a person can trust.** A number is more useful when the app can also say,
   in plain words, *why it matters* — without hiding behind an opaque model.

Loaf & Ledger is a focused attempt at all three, scoped deliberately to a **local,
single-user, self-hosted** deployment.

---

## 2. Design decisions

Each decision below was made against a concrete alternative; the rationale is what
mattered for this brief.

| Area | Decision | Why |
|------|----------|-----|
| **Repo** | Monorepo, `backend/` + `frontend/` | Atomic cross-stack changes for a solo build; JS workspaces add nothing across a Python backend. |
| **Tax engine** | Strategy interface + per-region config data | Bracket *logic* lives in code (testable, expressive); the *numbers* live in versionable config. Adding a region is a new rule; a new tax year is new data. |
| **Schema** | Normalized; `region` as a column; computed breakdown stored as **JSONB snapshot** | One schema serves every region, and each saved salary keeps its line-item breakdown so history survives later rule changes. |
| **Auth** | None (single implicit user) | The brief is a local, self-hosted, single-user app. A seam is left for an optional app password without a schema change. |
| **Currency** | Store native amount + code; **convert only for display** | Avoids lossy stored conversions; switching display currency never rewrites data. Rates come from a static, seeded table (offline-friendly). |
| **Tax depth** | Full statutory brackets + contributions, **national level** | PH/AU national regimes, US federal-only, EU modelled via Germany. An extensible jurisdiction model leaves room for US states / other EU countries. |
| **Insights** | Deterministic rule-based heuristics | Transparent and explainable; no ML infrastructure, no black box for money advice. |
| **Frontend state** | TanStack Query (server) + Zustand (global filters) | The app is read-heavy and cache-friendly; a single Zustand store holds region/currency/time-range and cascades to every query. |
| **Datastore** | SQLite for dev/tests, PostgreSQL for prod | Zero-config local runs; production keeps JSONB via a SQLAlchemy type variant. `DATABASE_URL` selects the backend. |

---

## 3. Architecture

```
                     ┌─────────────────────── frontend/ (Vite + React + TS) ───────────────────────┐
                     │  Zustand store { region, currency, timeRange, theme } ─ cascades to reads    │
                     │  TanStack Query hooks ─────────────▶  /api/v1/*                              │
                     └────────────────────────────────────────┬────────────────────────────────────┘
                                                               │  (Vite dev proxy)
                     ┌─────────────────────────────────────────▼───────────────── backend/ (FastAPI) ┐
   routers (F1–F6) ▶  salary · ledger · analytics · budgets · export · dashboard · meta              │
   services        ▶  tax engine · currency conversion · analytics/insights · single-user            │
   models          ▶  users · salary_profiles · transactions · categories · budgets · jurisdictions  │
                     │                                                         · exchange_rates       │
                     └────────────────────────────────────────────────────────────────────────────── ┘
                                   Alembic migrations · SQLite (dev) / PostgreSQL (prod)
```

**Feature → endpoint map**

| Feature | Endpoints |
|---|---|
| F1 Salary | `POST /salary/calculate`, `…/profiles` CRUD + `…/activate` |
| F2 Ledger | `/ledger/categories`, `/ledger/transactions` CRUD |
| F3 Analytics | `/analytics/overview`, `/analytics/monthly` |
| F4 Budgets | `/budgets` CRUD, `/budgets/status` |
| F5 Export | `/export/expenses.csv` (streamed) |
| F6 Dashboard | `/dashboard/summary` (honors global filters) |

---

## 4. Method: the tax engine

The heart of the app is `app/tax/`. A `TaxRule` abstract base defines
`compute_annual(gross, year) -> Breakdown`; each region is a small module that holds its
bracket/contribution constants and registers itself:

```
compute(gross, region, pay_period) ─▶ annualize ─▶ region rule ─▶ Breakdown
       Breakdown = { gross, per-line items (tax / social / info), net,
                     totals, effective_rate }  ── serialized to JSONB on save
```

Shared math (`progressive_tax`, `capped_contribution`) is factored out and unit-tested, so
each region file expresses *only* what's specific to that regime. Highlights of the
modelled rules:

- **PH** — TRAIN progressive brackets on income net of SSS / PhilHealth / Pag-IBIG (with
  their statutory floors and ceilings).
- **US** — 2025 federal single-filer brackets on income after the standard deduction, plus
  Social Security (to the wage base) and Medicare (with the additional-Medicare surtax).
- **AU** — 2024–25 resident PAYG brackets + 2% Medicare levy; superannuation shown as an
  *employer* line, not a deduction.
- **EU (Germany)** — the 2024 income-tax formula plus employee shares of pension, health,
  unemployment, and long-term-care insurance, each capped.

> These are planning-grade approximations, not tax-filing figures. A notable, *correct*
> consequence: below the statutory contribution floors the PH effective rate is
> **regressive** — a property the test suite explicitly accounts for.

---

## 5. Results: what the app does

The six features (F1–F6) are all implemented and wired end to end; see
[`WALKTHROUGH.md`](./WALKTHROUGH.md) for the user-facing tour. The visual identity is
deliberately a **household ledger book**: monospace tabular figures in every money slot,
faint "greenbar" row striping, and the accountant's double rule under a grand total.

---

## 6. Evaluation

- **Unit tests** cover the tax engine against hand-verified figures for all four regions,
  the annualization path, the net = gross − deductions invariant, and bracket edge cases.
- **Integration tests** drive the API through FastAPI's `TestClient` on SQLite: salary
  calculate-vs-persist, category/direction guards, currency-converted dashboards, budget
  upsert + status, and CSV export.
- **End-to-end:** the SPA, its dev proxy, and the API were exercised together — reads and
  writes — against the seeded database.

```bash
cd backend && uv run pytest      # 23 passing
cd frontend && npm run build     # typecheck + production build
```

---

## 7. Limitations & roadmap

- **Jurisdictions** are national-level only; US states and individual EU countries are
  deliberately out of scope for v1 but the `jurisdictions` model is built to grow.
- **Tax years** are current-year; the schema already carries a `year` field, so multi-year
  support is a data-only addition.
- **Exchange rates** are static and manually refreshed — a conscious trade for offline,
  dependency-free operation. A live-rate adapter is a natural next step.
- **Auth** is intentionally absent; the optional single app-password seam is unbuilt.

---

## 8. Project layout

```
Loaf-and-Ledger/
├── backend/          FastAPI + SQLAlchemy + Alembic; the tax engine lives in app/tax/
│   ├── app/{models,routers,services,tax,schemas.py,seed.py,main.py}
│   ├── migrations/   Alembic
│   └── tests/{unit,integration}
├── frontend/         Vite + React + TS; TanStack Query + Zustand
│   └── src/{api,components,pages,store,lib}
├── README.md · WALKTHROUGH.md · CHANGELOGS.md
```

## 9. Getting started

See [`WALKTHROUGH.md`](./WALKTHROUGH.md#setup). In short: `uv sync` + `alembic upgrade
head` + `python -m app.seed` + `uvicorn` for the API, `npm install` + `npm run dev` for the
UI, then open http://localhost:5173.

---

*Loaf & Ledger is licensed for personal use. Tax computations are estimates for planning
and must not be relied upon for filing.*
