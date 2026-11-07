# Clean UI/UX testing

Use this guide to test empty states and build up financial data by hand. For startup
commands, see [the walkthrough](../WALKTHROUGH.md#setup). For sample financial activity,
use its separate [optional demo data](../WALKTHROUGH.md#optional-demo-data) instructions.

## Baseline established on 2026-11-07

The local SQLite database was reset in one transaction after a verified backup. All
financial records, including voided entries and archived/custom accounts, were removed.
The 36 built-in account definitions were recreated with zero opening balances. The
existing user, schema revision, theme, and independent section-period settings were retained.

These counts record the reset result; they will change as UI/UX tests create data.

| Record | Before reset | After reset |
|---|---:|---:|
| Users | 1 | 1 |
| Accounts | 36 | 36 active built-in accounts |
| Journal entries | 65 | 0 |
| Journal lines | 161 | 0 |
| Saved salary profiles | 1 | 0 |
| Budgets | 9 | 0 |
| Payees | 7 | 0 |
| Fund overrides | 0 | 0 |

All account balances and Dashboard financial totals were zero. The rebuilt warehouse
contained 36 account dimension rows, no financial facts or monthly/daily aggregates,
and zero drift. SQLite integrity and foreign-key checks passed.

The built-in accounts include the gross-salary and statutory-deduction codes used by
payslip posting. Keeping them makes salary and entry-form testing possible immediately.

## Start testing

For this existing reset database, run migrations and start the backend from `backend/`:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Start `npm run dev` from `frontend/`, open `http://localhost:5173`, and reload any
previously open tab. Reloading clears in-memory query results while preserving theme
and section-period selections in browser storage. The reset operation did not start
either server.

`uv run python -m app.seed` creates demo activity when the ledger is empty. Keep it out
of this startup sequence to preserve empty-state tests. On a brand-new database, use
the walkthrough's [chart-only initialization](../WALKTHROUGH.md#clean-database-setup).

## Smoke-test checklist

| Area | Exercise | Expected result |
|---|---|---|
| Empty state | Open Dashboard, Accounts, Salary, Ledger, Budgets, and Analytics before creating records. | Accounts contains 36 zero-balance accounts; Ledger, salary profiles, and budgets are empty; financial totals are zero. Bounded chart periods can show flat zero activity. |
| Period scope | Change Dashboard to All, Accounts to YTD, and leave Analytics on This month; navigate and reload. | Each section retains its own choice. Budgets remains on the current month, and Ledger shows all dates. The top bar contains the theme control. |
| Desktop/mobile | Inspect at 1440px, 1024px, and 390px widths, then check the 1200px breakpoint. | Summary cards form four, two, and one column respectively; charts pair on desktop; the page does not overflow horizontally. |
| Long tables | Use enough activity or a temporary response fixture to exceed a dashboard table's available height. | The table scrolls within a 480px maximum-height area; column headers remain visible. |
| Accounts | Check Add an account placement; collapse/reopen Overview and account groups using mouse and keyboard. | The form appears first, followed by the period selector. Each disclosure operates independently. |
| Period balances | Record activity before and within the selected period. | Period debits/credits include only selected dates; closing balances include earlier activity through the end date. Trial balance CSV still covers all dates. |
| Salary | Calculate gross `15003` with Fortnightly, using the existing 2025 rules. | Annual gross is `390078.00`; period net is `13307.19`; deductions show percentages of period gross. |
| Profiles | Save two different profiles, calculate a preview, switch profiles, and edit the gross input. | Gross/net/period columns describe each saved profile. Switching loads its inputs and clears previous preview/posting feedback. Saving requires a calculation matching the current inputs. |
| Profile errors | Simulate a failed activation and delete an inactive profile. | Failure preserves the current profile; deletion does not activate the deleted row. |
| Payslip | Post the current profile into an asset account, then retry posting that same profile. | One balanced entry is created; its deposit equals displayed net pay. The retry returns the same entry. The one-post-per-profile rule still applies. |
| Ledger pages | Create at least 11 entries, use Previous/Next, post from a later page, and void the only entry on the last page. | Pages show ten entries, then the remainder; posting returns to page one; voiding moves to the last valid page. Cash balances and summary totals span complete history. |
| Page errors | Simulate a failed ledger page load, then retry or navigate back. | An error and Retry control appear; Previous remains usable when there is a previous page. |
| Warehouse | After posting, check `/api/v1/warehouse/status` and the affected analytics. | Data appears without a manual rebuild; status remains healthy with zero drift. |

Creating these scenarios intentionally changes the baseline. Normal void/archive actions
preserve historical records; they do not recreate a completely empty database.

## Check the baseline without changing data

From `backend/`, the following checks the default SQLite database in read-only mode.
It reports counts and succeeds only when the clean baseline still exists:

```bash
uv run python - <<'PY'
import sqlite3
from pathlib import Path

path = Path("loaf_ledger.db").resolve()
with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
    expected = {
        "users": 1, "accounts": 36, "journal_entries": 0, "journal_lines": 0,
        "salary_profiles": 0, "budgets": 0, "payees": 0, "fund_overrides": 0,
    }
    actual = {
        table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in expected
    }
    print(actual)
    assert actual == expected, "Test data differs from the clean baseline"
    assert db.execute(
        "SELECT COUNT(*) FROM accounts WHERE is_active = 1 AND is_system = 1 "
        "AND archived_at IS NULL AND opening_balance = 0"
    ).fetchone()[0] == 36
    assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
print("Clean SQLite baseline verified")
PY
```

If `DATABASE_URL` points elsewhere, inspect that configured database instead. With the API
running, check the response from:

```bash
curl -fsS http://localhost:8000/api/v1/warehouse/status
```

For the baseline, expect `ok: true`, `drift: 0`, `oltp_lines: 0`, `olap_lines: 0`,
and an empty `integrity_problems` list. Static calendar/source dimension rows remain
in the warehouse even though financial facts are empty.

## Backup and recovery

The pre-reset source-of-truth backup is stored locally at:

```text
backend/backups/loaf_ledger-before-reset-20261107-230341-205585.sqlite3
```

It was created through SQLite's backup API, with integrity and foreign-key checks
passing before deletion. The file contains the **pre-reset financial history**, not the
clean baseline. SQLite backups are ignored by Git and are not included in a fresh clone.
The derived warehouse can be rebuilt from this backup after restoring it.

To recover that prior history, stop the API and other clients using these database files.
From `backend/`, for the default SQLite configuration:

```bash
uv run python - <<'PY'
import sqlite3
from pathlib import Path

backup = Path("backups/loaf_ledger-before-reset-20261107-230341-205585.sqlite3").resolve()
with sqlite3.connect(f"{backup.as_uri()}?mode=ro", uri=True) as source:
    assert source.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    with sqlite3.connect("loaf_ledger.db") as target:
        source.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert not target.execute("PRAGMA foreign_key_check").fetchall()
print("Pre-reset history restored")
PY
uv run alembic upgrade head
uv run python -m app.warehouse.rebuild
```

Restart the servers and reload the browser. Restore into the configured SQLite path if
it differs from the default; the example above specifically targets `backend/loaf_ledger.db`.

## Repeating a clean reset

A full clean reset is a maintenance operation, separate from normal UI deletion:

1. Stop financial writes, confirm the configured database paths, and create/verify a
   timestamped SQLite backup.
2. In one transaction, delete journal lines, journal entries, budgets, fund overrides,
   payees, salary profiles, and accounts in foreign-key-safe order. Include voided and
   archived records; preserve users and the migration revision.
3. Restore only the 36 definitions from `app.seed.CHART`, with active/system flags and
   zero opening balances, before committing. `seed_chart()` commits internally, so a
   transaction that combines deletion and restoration must insert the definitions directly.
4. Rebuild the warehouse through the running API, or use its CLI with the API stopped.
5. Verify the counts and zero financial totals above, check integrity/warehouse drift,
   and reload open tabs.

The demo loader is not part of this operation. Keep the backup path and final counts
in the reset report, as was done for the baseline recorded here.
