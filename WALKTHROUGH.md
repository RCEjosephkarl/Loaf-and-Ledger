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
uv run python -m app.seed        # PH chart of accounts + four months of PHP demo entries
uv run uvicorn app.main:app --reload   # serves http://localhost:8000
```

The seed writes **both** databases: the ledger first, then a full load of the analytics
warehouse.

> **Seed with the server stopped.** DuckDB allows one writer per file, so if uvicorn is
> already running it holds `warehouse.duckdb` and the seed cannot load it. The ledger half
> still succeeds and the command tells you so, exits non-zero, and points at the two ways
> to finish:
>
> ```bash
> curl -X POST localhost:8000/api/v1/warehouse/rebuild   # in-process, no downtime
> ```
>
> …or stop the server and re-run the seed. The same applies to the standalone reload:
>
> ```bash
> uv run python -m app.warehouse.rebuild
> ```

The warehouse is derived data, so deleting `warehouse.duckdb` costs nothing but a rebuild.

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
> code runs on PostgreSQL (the `breakdown` column becomes real JSONB). `WAREHOUSE_PATH`
> points the OLAP store somewhere else independently.

---

## Theme and section periods

The top bar controls **Theme** — light → dark → follow-system.

**Dashboard**, **Accounts**, and **Analytics** each have their own period control:
This month · Last 3 months · YTD · All. Each selection persists independently between
visits. Last 3 months includes the current month; YTD ends today. All includes complete
history, and charts include calendar dates with no activity.

**Budgets** always shows the current month. **Ledger** shows all dates, ten entries at a
time. Account selection belongs to entry forms rather than a global filter.

---

## First, the idea

Every movement of money is recorded as a **journal entry** with two or more **lines**, and
an entry's debits always equal its credits. You mostly won't type debits and credits — the
quick form writes both sides for you — but it is why the app can do things a flat list of
transactions cannot:

- **A trial balance that ties.** Every account's debit and credit totals, and the two
  columns match. Download it from the Accounts page.
- **Transfers that aren't spending.** Moving ₱5,000 into savings touches two of *your*
  accounts, so it is a transfer. It moves your balances and never touches your expenses or
  your savings rate.
- **A payslip as one fact.** Gross earned, each withholding taken, the remainder banked —
  one entry with six lines, not six unrelated rows.

---

## The tour

### 01 Dashboard — "Where the dough goes"
Your balance sheet gets the bold "highlight card" treatment — credits in, debits out, and
net cashflow drawn with the accountant's double underline on a filled blue ground,
so it reads first. Alongside it: your savings rate, your **net worth** (assets less
liabilities at the selected closing date), and how much you **moved rather than spent** this period.

Below, paired charts show balance over time and monthly income/expense/net. The next row
pairs **plain-language notes** with biggest expenses. Long tables scroll inside their cards.

### 02 Salary — "What survives to net"
1. Enter your **gross** pay and choose **monthly**, **fortnightly** (every two weeks, 26 payments/year), or **annual**.
2. Hit **Calculate**: SSS, PhilHealth, Pag-IBIG and income tax, then your net take-home
   and the share you keep. Each deduction also shows its percentage of gross pay. Contributions
   are deducted *before* the TRAIN brackets apply.
3. **Save profile** to persist it. Saved profiles show period, gross, and net salary. Click a
   profile to make it current: its inputs and breakdown load into the calculator and it becomes
   the posting target. Editing calculator inputs requires a matching calculation before saving.
4. **Post to ledger** — pick which asset account the net pay lands in, and the app writes
   the whole payslip as one balanced entry. A profile posts once; pressing it again tells
   you which entry it already made.

### 03 Accounts — "Every pocket, named"
**Add an account** appears first. The period selector controls debit/credit activity while
closing balances include earlier postings. Overview and each account-type group expand or
collapse independently using their headers, including with the keyboard. Assets 1xxx, liabilities 2xxx, equity 3xxx, income 4xxx, spending 5xxx, statutory
6xxx — a convention, not a rule the app enforces.

Nothing here is stored as a running total; every balance is computed from the journal, so
the books can always be reproduced from their entries. **Add an account** for anything the
seed missed. Removing one **archives** it — an account with postings can never be deleted,
or its historical lines would lose their meaning.

> Note what's *absent*: there is no "Savings & investment" expense account. Money moved
> into savings is a transfer between assets, which is the whole point.

### 04 Ledger — "Every entry, dated and dressed"
**The quick way** — pick **Money out**, **Money in**, or **Transfer**, then two accounts:
where the money came from or landed, and the category or source. Enter an amount, a date
and time, optionally a payee and a note, and post. The app writes both sides.

**The advanced way** — open **Advanced · journal entry** for anything with more than two
lines: a split bill, a part-payment, a hand-entered payslip. Add lines, mark each debit or
credit, and watch the meter: `Debits ₱X · Credits ₱Y`. The submit button stays disabled
until it says **✓ balanced**, so an unbalanced entry is unpostable rather than merely
rejected.

In the list, click any row to expand it and see both sides. The running **cash balance**
column spans your whole history, including archived asset accounts. Previous/Next moves
through ten entries at a time without resetting balances. Totals and CSV export cover all dates. **Voiding** an entry keeps the row, marked
void: a ledger you can silently erase from is not auditable.

**Export ledger CSV** gives one row per journal line, so the books are reconstructable from
the file alone.

### 05 Budgets — "Limits, and how close you are"
Set a monthly limit on any expense account. The table shows limit, spent, remaining and a
utilization bar that turns amber then red as you pass 100%. Spend is read from the same
warehouse the Analytics page uses, so the two can never disagree.

The **initial fund** is what you had going into the period — by default the cumulative net
cash flow the day before it started, overridable if your books began mid-stream.

### 06 Analytics — "The story your money tells"
The flagship. Four acts, in the order the questions matter, with a sticky nav on the left:

- **I · What came in** — a gross-to-net **waterfall**. Each bar hangs from where the last
  one ended, so you watch every withholding take its bite instead of reading five numbers
  and doing the subtraction yourself. Beside it, every source of income ranked.
- **II · Where it went** — expenses ranked with a delta against the prior period of equal
  length, and the monthly mix stacked by account. Transfers are named and excluded.
- **III · What's left** — cumulative cash flow, your burn rate per day/week/month, and how
  many days your current cash covers at that rate.
- **IV · What it means** — the deterministic notes, plus the figures behind the whole
  story in one table.

If analytics ever fall behind the ledger, a banner appears at the top with a **Rebuild
warehouse** button. In normal use you will never see it: every entry you post is loaded
into the warehouse before the request returns.

## Tips

- **Statutory vs. discretionary.** The four 6xxx accounts (BIR, SSS, PhilHealth, Pag-IBIG)
  are flagged statutory, so analytics can tell you what was withheld before you had a
  choice, separately from what you decided to spend.
- **Use Transfer, not an expense, for savings.** That is what keeps your savings rate
  honest — and the Dashboard reports the total you moved as its own figure, so putting
  money aside still shows up as something you did.
- **Filter by account** to answer "what did this card actually pay for". The whole entry
  comes back, both sides, not just the matching line.
- **The two databases.** `loaf_ledger.db` is the system of record; `warehouse.duckdb` is
  derived and safe to delete. If they ever drift, the Analytics page says so and offers a
  rebuild. From the shell, `uv run python -m app.warehouse.rebuild` does the same — but
  stop the server first, since DuckDB allows one writer per file.
- **Prove the books.** Accounts → *Trial balance CSV*. The debit and credit columns tie, or
  something is wrong; `GET /warehouse/status` also runs an integrity check over every entry.
