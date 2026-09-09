"""Load the OLTP journal into the star schema.

Two entry points matter:

* :func:`apply_entry` runs on the write path, immediately after a ledger
  commit, so a new earning is queryable in analytics before the HTTP response
  returns. It is idempotent — it deletes the entry's fact rows and re-inserts
  them — which makes edits and replays free.
* :func:`rebuild_all` truncates and reloads everything, for recovery, schema
  changes, or verifying that write-through has not drifted.

A warehouse failure is never allowed to fail a ledger write. Callers wrap
:func:`apply_entry` and fall back to :func:`mark_stale`; the OLTP database
remains the system of record and /warehouse/status reports the drift.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.base import AccountType, flow_class, normal_balance
from app.models.journal import JournalEntry
from app.models.payee import Payee
from app.models.salary import SalaryProfile
from app.warehouse import ddl
from app.warehouse.engine import WarehouseError, cursor

log = logging.getLogger(__name__)

ZERO = Decimal("0")
_FLOW_ACCOUNTS = (AccountType.INCOME, AccountType.EXPENSE)


def date_key(value: date | datetime) -> int:
    d = value.date() if isinstance(value, datetime) else value
    return d.year * 10000 + d.month * 100 + d.day


# ------------------------------------------------------------------- dimensions


def sync_accounts(db: Session, conn) -> None:  # noqa: ANN001
    """Mirror the chart of accounts into dim_account.

    Rewritten wholesale rather than incrementally: the chart is a few dozen
    rows, and a full refresh means a renamed or archived account can never
    leave a stale label behind on historical facts.
    """
    accounts = db.execute(select(Account).order_by(Account.id)).scalars().all()
    conn.execute("DELETE FROM dim_account")
    if not accounts:
        return
    conn.executemany(
        "INSERT INTO dim_account (account_key, account_id, code, name, type, subtype, "
        "is_statutory, normal_balance, flow_class, is_active) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                a.id,
                a.id,
                a.code,
                a.name,
                a.type.value,
                a.subtype,
                bool(a.is_statutory),
                normal_balance(a.type),
                flow_class(a.type).value,
                bool(a.is_active and a.archived_at is None),
            )
            for a in accounts
        ],
    )


def sync_payees(db: Session, conn) -> None:  # noqa: ANN001
    payees = db.execute(select(Payee).order_by(Payee.id)).scalars().all()
    conn.execute("DELETE FROM dim_payee")
    if payees:
        conn.executemany(
            "INSERT INTO dim_payee (payee_key, payee_id, name) VALUES (?,?,?)",
            [(p.id, p.id, p.name) for p in payees],
        )


# ------------------------------------------------------------------- facts


def _entry_rows(entry: JournalEntry, accounts: dict[int, Account]) -> list[tuple]:
    """Flatten one entry into its fact rows."""
    transfer = all(accounts[ln.account_id].type not in _FLOW_ACCOUNTS for ln in entry.lines)
    dk = date_key(entry.occurred_at)
    skey = ddl.source_key(entry.source)
    rows = []
    for line in entry.lines:
        account = accounts[line.account_id]
        debit = Decimal(str(line.debit or ZERO))
        credit = Decimal(str(line.credit or ZERO))
        signed = debit - credit if normal_balance(account.type) == "dr" else credit - debit
        rows.append(
            (
                line.id,
                entry.id,
                dk,
                entry.occurred_at,
                line.account_id,
                entry.payee_id,
                skey,
                debit,
                credit,
                signed,
                debit + credit,  # exactly one side is non-zero
                transfer,
                line.memo or entry.memo,
            )
        )
    return rows


def _delete_entry_facts(conn, entry_id: int) -> None:  # noqa: ANN001
    conn.execute("DELETE FROM fact_ledger_line WHERE entry_id = ?", [entry_id])


def apply_entry(db: Session, entry_id: int) -> None:
    """Load (or reload, or remove) one entry's facts and refresh its rollups.

    Handles all three write cases uniformly: a new entry inserts, an amended
    entry replaces, and a voided or deleted entry leaves nothing behind.
    """
    entry = db.get(JournalEntry, entry_id)
    try:
        with cursor() as conn:
            # The months/days to refresh include wherever the entry *used* to
            # sit, or moving an entry's date would strand the old rollup.
            touched = set(
                conn.execute(
                    "SELECT DISTINCT date_key FROM fact_ledger_line WHERE entry_id = ?",
                    [entry_id],
                ).fetchall()
            )
            affected_days = {row[0] for row in touched}

            _delete_entry_facts(conn, entry_id)

            if entry is not None and entry.voided_at is None and entry.lines:
                accounts = {
                    a.id: a
                    for a in db.execute(
                        select(Account).where(
                            Account.id.in_({ln.account_id for ln in entry.lines})
                        )
                    )
                    .scalars()
                    .all()
                }
                sync_accounts(db, conn)
                sync_payees(db, conn)
                rows = _entry_rows(entry, accounts)
                conn.executemany(
                    "INSERT INTO fact_ledger_line (line_id, entry_id, date_key, occurred_at, "
                    "account_key, payee_key, source_key, debit, credit, signed_amount, amount, "
                    "is_transfer, memo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                affected_days.add(date_key(entry.occurred_at))

            _refresh_monthly(conn, {d // 100 for d in affected_days})
            _refresh_daily_cashflow(conn)
            _touch_watermark(conn, db)
    except WarehouseError:
        raise
    except Exception as exc:  # duckdb errors are not a single base class
        raise WarehouseError(f"Failed to apply entry {entry_id}: {exc}") from exc


def apply_payslip(db: Session, profile_id: int) -> None:
    """Reload one salary profile's breakdown into fact_payslip_item."""
    profile = db.get(SalaryProfile, profile_id)
    try:
        with cursor() as conn:
            conn.execute("DELETE FROM fact_payslip_item WHERE profile_id = ?", [profile_id])
            if profile is not None:
                conn.executemany(
                    "INSERT INTO fact_payslip_item (payslip_item_id, profile_id, date_key, "
                    "tax_year, pay_period, item_key, item_label, kind, amount, amount_annual, "
                    "is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    _payslip_rows(profile),
                )
            _touch_watermark(conn, db)
    except Exception as exc:
        raise WarehouseError(f"Failed to apply payslip {profile_id}: {exc}") from exc


def _payslip_rows(profile: SalaryProfile) -> list[tuple]:
    breakdown = profile.breakdown or {}
    updated = profile.updated_at or profile.created_at or datetime.utcnow()
    rows = []
    for item in breakdown.get("items", []):
        rows.append(
            (
                f"{profile.id}:{item['key']}",
                profile.id,
                date_key(updated),
                int(breakdown.get("tax_year", profile.tax_year)),
                breakdown.get("pay_period", profile.pay_period.value),
                item["key"],
                item["label"],
                item["kind"],
                Decimal(str(item.get("amount_period", item.get("amount", "0")))),
                Decimal(str(item.get("amount", "0"))),
                bool(profile.is_active),
            )
        )
    return rows


# ------------------------------------------------------------------ rollups


def _refresh_monthly(conn, month_keys: set[int]) -> None:  # noqa: ANN001
    """Recompute agg_monthly_account for just the months a write touched.

    `inflow`/`outflow` are cash-flow figures and read only from income and
    expense accounts; balance-sheet accounts contribute to `net_amount` alone.
    A transfer therefore scores zero on both sides for free, because every one
    of its lines is a balance-class account.
    """
    if not month_keys:
        return
    placeholders = ",".join("?" for _ in month_keys)
    params = list(month_keys)
    conn.execute(
        f"DELETE FROM agg_monthly_account WHERE month_key IN ({placeholders})", params
    )
    conn.execute(
        f"""
        INSERT INTO agg_monthly_account (month_key, account_key, inflow, outflow,
                                         net_amount, entry_count)
        SELECT
            d.month_key,
            f.account_key,
            SUM(CASE WHEN a.flow_class = 'inflow'  THEN f.signed_amount ELSE 0 END),
            SUM(CASE WHEN a.flow_class = 'outflow' THEN f.signed_amount ELSE 0 END),
            SUM(f.signed_amount),
            CAST(COUNT(DISTINCT f.entry_id) AS INTEGER)
        FROM fact_ledger_line f
        JOIN dim_date    d ON d.date_key = f.date_key
        JOIN dim_account a ON a.account_key = f.account_key
        WHERE d.month_key IN ({placeholders})
        GROUP BY d.month_key, f.account_key
        """,
        params,
    )


def _refresh_daily_cashflow(conn) -> None:  # noqa: ANN001
    """Rebuild agg_daily_cashflow in full.

    The cumulative balance is a running total, so a change on any day rewrites
    every later day anyway; with one row per day that saw activity, a full
    recompute is both simpler and cheaper than working out the tail to patch.
    """
    conn.execute("DELETE FROM agg_daily_cashflow")
    conn.execute(
        """
        INSERT INTO agg_daily_cashflow (date_key, inflow, outflow, net, cumulative_balance)
        WITH daily AS (
            SELECT
                f.date_key,
                SUM(CASE WHEN a.flow_class = 'inflow'  THEN f.signed_amount ELSE 0 END) AS inflow,
                SUM(CASE WHEN a.flow_class = 'outflow' THEN f.signed_amount ELSE 0 END) AS outflow
            FROM fact_ledger_line f
            JOIN dim_account a ON a.account_key = f.account_key
            GROUP BY f.date_key
        )
        SELECT
            date_key,
            inflow,
            outflow,
            inflow - outflow,
            SUM(inflow - outflow) OVER (ORDER BY date_key
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        FROM daily
        ORDER BY date_key
        """
    )


# --------------------------------------------------------------- watermark


def _touch_watermark(conn, db: Session, *, stale: bool = False, note: str | None = None) -> None:  # noqa: ANN001
    from sqlalchemy import func

    from app.models.journal import JournalLine

    source_rows = db.execute(
        select(func.count())
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.voided_at.is_(None))
    ).scalar_one()
    target_rows = conn.execute("SELECT count(*) FROM fact_ledger_line").fetchone()[0]
    conn.execute("DELETE FROM etl_watermark WHERE table_name = 'fact_ledger_line'")
    conn.execute(
        "INSERT INTO etl_watermark (table_name, last_loaded_at, source_rows, target_rows, "
        "is_stale, note) VALUES ('fact_ledger_line', ?, ?, ?, ?, ?)",
        [datetime.utcnow(), source_rows, target_rows, stale, note],
    )


def mark_stale(note: str) -> None:
    """Record that the warehouse missed a write.

    Best-effort by design: if the warehouse is unreachable this cannot be
    written either, and the row-count comparison in /warehouse/status will
    still catch the drift.
    """
    try:
        with cursor() as conn:
            conn.execute(
                "UPDATE etl_watermark SET is_stale = TRUE, note = ? WHERE table_name = ?",
                [note[:500], "fact_ledger_line"],
            )
    except Exception:  # pragma: no cover - the fallback's fallback
        log.exception("Could not mark the warehouse stale")


# ------------------------------------------------------------------ rebuild


def rebuild_all(db: Session, user_id: int | None = None) -> dict[str, int]:
    """Truncate and reload every fact and mutable dimension."""
    entries_stmt = select(JournalEntry).where(JournalEntry.voided_at.is_(None))
    profiles_stmt = select(SalaryProfile)
    if user_id is not None:
        entries_stmt = entries_stmt.where(JournalEntry.user_id == user_id)
        profiles_stmt = profiles_stmt.where(SalaryProfile.user_id == user_id)

    entries = db.execute(entries_stmt.order_by(JournalEntry.occurred_at)).scalars().all()
    accounts = {a.id: a for a in db.execute(select(Account)).scalars().all()}
    profiles = db.execute(profiles_stmt).scalars().all()

    try:
        with cursor() as conn:
            ddl.truncate_all(conn)
            sync_accounts(db, conn)
            sync_payees(db, conn)

            rows: list[tuple] = []
            months: set[int] = set()
            for entry in entries:
                if not entry.lines:
                    continue
                rows.extend(_entry_rows(entry, accounts))
                months.add(date_key(entry.occurred_at) // 100)
            if rows:
                conn.executemany(
                    "INSERT INTO fact_ledger_line (line_id, entry_id, date_key, occurred_at, "
                    "account_key, payee_key, source_key, debit, credit, signed_amount, amount, "
                    "is_transfer, memo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )

            payslip_rows: list[tuple] = []
            for profile in profiles:
                payslip_rows.extend(_payslip_rows(profile))
            if payslip_rows:
                conn.executemany(
                    "INSERT INTO fact_payslip_item (payslip_item_id, profile_id, date_key, "
                    "tax_year, pay_period, item_key, item_label, kind, amount, amount_annual, "
                    "is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    payslip_rows,
                )

            _refresh_monthly(conn, months)
            _refresh_daily_cashflow(conn)
            _touch_watermark(conn, db)

            return {
                "entries": len(entries),
                "fact_ledger_line": len(rows),
                "fact_payslip_item": len(payslip_rows),
                "dim_account": len(accounts),
                "agg_monthly_account": conn.execute(
                    "SELECT count(*) FROM agg_monthly_account"
                ).fetchone()[0],
                "agg_daily_cashflow": conn.execute(
                    "SELECT count(*) FROM agg_daily_cashflow"
                ).fetchone()[0],
            }
    except WarehouseError:
        raise
    except Exception as exc:
        raise WarehouseError(f"Rebuild failed: {exc}") from exc


def safe_apply_entry(db: Session, entry_id: int) -> bool:
    """Write-through wrapper for routers: never raises.

    Returns whether the warehouse took the write. A False means the ledger
    committed but analytics are behind, which /warehouse/status surfaces.
    """
    try:
        apply_entry(db, entry_id)
        return True
    except Exception as exc:
        log.exception("Warehouse write-through failed for entry %s", entry_id)
        mark_stale(f"entry {entry_id}: {exc}")
        return False


def safe_apply_payslip(db: Session, profile_id: int) -> bool:
    try:
        apply_payslip(db, profile_id)
        return True
    except Exception as exc:
        log.exception("Warehouse write-through failed for payslip %s", profile_id)
        mark_stale(f"payslip {profile_id}: {exc}")
        return False
