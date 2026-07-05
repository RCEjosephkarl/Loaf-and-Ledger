# Loaf & Ledger — Walkthrough

A hands-on manual for using the app day to day. If you just want to get it running,
start with **Setup**; if it's already running, skip to **The tour**.

---

## Setup

You need **Python 3.12**, **Node 20+**, and (for local use) nothing else — the app
defaults to a self-contained SQLite database.

### 1. Backend

```bash
cd backend
uv sync --extra dev              # install pinned deps into a Python 3.12 venv
uv run alembic upgrade head      # create the database schema
uv run python -m app.seed        # seed your profile + reference data + a demo month
uv run uvicorn app.main:app --reload   # serves http://localhost:8000
```

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev                      # serves http://localhost:5173
```

Open **http://localhost:5173**. The frontend proxies API calls to the backend, so both
need to be running. Works on desktop and Android browsers.

> **Production note:** set `DATABASE_URL` to a `postgresql+psycopg://…` URL and the same
> code runs on PostgreSQL (the `breakdown` column becomes real JSONB).

---

## The global bar

Everything on screen answers to the bar across the top:

- **Time range** — This month · Last 3 months · YTD · All.
- **Region** — filter to one region (PH/US/AU/EU) or All.
- **Currency** — the display currency. Amounts are stored in their original currency and
  converted for display, so switching here never rewrites your data.
- **Theme** — cycles light → dark → follow-system.

Your choices persist between visits.

---

## The tour

### Dashboard — "Where the dough goes"
Your running balance sheet: credits in, debits out, and net cashflow drawn with the
accountant's double underline. Alongside it: your savings rate, your active salary's net
pay, and **plain-language notes** — e.g. a warning when spending outruns income, or a flag
when one category eats most of your budget.

### Salary — "Gross in, net out"
1. Pick a **region**, enter your **gross** pay, and choose **monthly** or **annual**.
2. Hit **Calculate** to see the breakdown: income tax and each statutory contribution,
   then your net take-home with the effective rate.
3. Toggle **Per period / Annual** to reframe the same numbers.
4. **Save & make active** to persist it. The active profile feeds the dashboard and
   analytics, and is remembered as your default input.
5. Saved profiles are listed below — activate or delete any of them.

> Australia's superannuation is shown as an *employer* line: it's on top of your salary,
> so it doesn't reduce take-home.

### Ledger — "Every entry, dated and dressed"
1. Choose **Debit (out)** or **Credit (in)**.
2. Pick a category, enter an amount, optionally set a region (which sets the entry's
   currency), a date, and a note.
3. **Record entry.** It appears in the list, credits in green, debits in red.
4. **Export expenses CSV** downloads the debit side for your current filters — with a
   converted-amount column in your chosen display currency.

### Budgets — "Lines drawn before you spend"
1. Choose the **month** and **year**.
2. Set a **monthly limit** for any expense category.
3. Each budget shows a fill bar — green while you're under, red when you've crossed it —
   with amount spent, percent used, and what's left.

### Analytics — "Cross-referenced"
The numbers from your salary and your ledger, side by side: total income and expense,
savings rate, and the share of gross lost to tax and contributions. Below, a six-month
income-vs-expense chart and category-level breakdowns for both sides.

---

## Tips

- **Multi-currency:** record a trip in EUR and your salary in USD; switch the top-bar
  currency to see everything reconciled either way.
- **Statutory vs. spending:** deductions computed by the salary engine are kept separate
  from your discretionary categories, so analytics reflects *behavior*, not payroll math.
- **Refreshing FX:** exchange rates are seeded and static. To update them, edit the
  `exchange_rates` table (or `FX_USD` in `backend/app/seed.py` and re-seed).
