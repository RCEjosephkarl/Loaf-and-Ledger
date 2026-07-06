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
Your running balance sheet gets the bold "highlight card" treatment — credits in, debits
out, and net cashflow drawn with the accountant's double underline, on a filled crust-brown
background so it reads first. Alongside it: your savings rate, your active salary's net
pay, and **plain-language notes** — e.g. a warning when spending outruns income, a flag
when one category eats most of your budget, or a nod when your income streams or spending
are well diversified.

Below that, a currency-rates panel shows each currency's **actual rate** on its own scale
(not a normalized percentage) — hover any point to see that day's value and its change from
the day before, both absolute and percent. It follows the global time range like everything
else, so switching to "YTD" shows a longer FX trend.

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
3. **Record entry.** It appears in the list, credits in green, debits in red. The entry
   list scrolls within its own panel once it gets long, so the page doesn't grow forever.
4. **Edit** any entry in place — category, amount, currency, date/time, and note are all
   changeable. Direction (debit/credit) is the one thing you can't flip on an existing
   entry; delete and re-add it instead.
5. **Export expenses CSV** downloads the debit side for your current filters — with a
   converted-amount column in your chosen display currency.

### Budgets — "Lines drawn before you spend"
1. Pick a **period** — Month, 3 months, YTD, or All — using the same segmented control as
   the global time range, but scoped to this page only; it doesn't affect other pages.
2. The **Initial fund** card (under the Trend tab) shows what you started the period with —
   defaulted to the prior period's ending balance, carried forward automatically. Edit it if
   your real starting point differs, or reset it back to the computed default.
3. Under **By category**, set a **monthly limit** for any expense category (limits are
   always set per calendar month, regardless of which period you're viewing) and see each
   one's fill bar — green while you're under, red once you've crossed it — aggregated over
   however many months your selected period covers, with amount spent, percent used, and
   what's left.
4. The KPI row (On track / At risk / Over budget / Projected period-end) and the running
   balance chart are both "hyperlocalized" to whichever period you've selected, starting
   from your initial fund.

### Analytics — "Cross-referenced"
The numbers from your salary and your ledger, side by side: total income and expense,
savings rate, and the share of gross lost to tax and contributions. Below that, three
hover-to-switch tabs (click one to keep it open):
- **Overview** — burn rate, and a monthly combo chart (income/expense bars with the net
  cash flow traced as a line).
- **Trends** — cumulative cash-flow trend and the change in expense between consecutive
  transactions.
- **Categories** — income/expense tables (with a Δ vs. the prior period) and a stacked
  chart showing how your top expense categories' mix has shifted month to month.

---

## Tips

- **Multi-currency:** record a trip in EUR and your salary in USD; switch the top-bar
  currency to see everything reconciled either way.
- **Statutory vs. spending:** deductions computed by the salary engine are kept separate
  from your discretionary categories, so analytics reflects *behavior*, not payroll math.
- **Refreshing FX:** rates refresh live from Frankfurter (ECB reference rates) whenever the
  Dashboard's FX panel is fetched, and are cached locally for a day at a time — no manual
  editing needed. If the network is unreachable, the app falls back to whatever was last
  cached rather than failing.
