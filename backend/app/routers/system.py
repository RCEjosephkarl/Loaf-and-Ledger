"""System & database management endpoints for Global Settings.

Supports:
* Database navigation: OLTP (SQLite/PostgreSQL) and OLAP (DuckDB) table row
  counts, file sizes, backup inventory, and safe table row previews.
* Clean baseline reset: backs up SQLite, clears financial records, restores
  the 36 built-in accounts at zero balance, and rebuilds the warehouse.
* Demo seeding: populates sample financial activity and rebuilds the warehouse.
* Granular & full data deletion: clears entries, budgets, salary profiles,
  custom accounts/payees, or all financial data while keeping stores in sync.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.account import Account
from app.models.budget import Budget, FundOverride
from app.models.journal import JournalEntry, JournalLine
from app.models.payee import Payee
from app.models.salary import SalaryProfile
from app.models.user import User
from app.schemas import (
    DatabaseOverviewOut,
    DataDeletionRequest,
    SystemOperationOut,
    TableInfoOut,
    TablePreviewOut,
)
from app.seed import CHART, seed_demo
from app.warehouse import etl, status
from app.warehouse.engine import WarehouseError, cursor, warehouse_path

router = APIRouter(prefix="/system", tags=["system"])

OLTP_TABLES: list[tuple[str, str, str]] = [
    ("users", "Core", "Single-user profile and local deployment metadata."),
    ("accounts", "Chart of Accounts", "Asset, liability, equity, income, and expense accounts."),
    ("payees", "Directory", "Saved merchants, employers, and counterparties."),
    ("journal_entries", "OLTP Journal", "Double-entry transaction headers with timestamps."),
    ("journal_lines", "OLTP Journal", "Individual balanced debit and credit postings."),
    ("budgets", "Planning", "Monthly spending limits per expense account."),
    ("fund_overrides", "Planning", "Period starting-balance overrides."),
    ("salary_profiles", "Payroll", "Saved PH statutory gross-to-net salary snapshots."),
]

OLAP_TABLES: list[tuple[str, str, str]] = [
    ("dim_date", "Dimension", "Calendar day dimension (year, month, quarter, weekday)."),
    ("dim_account", "Dimension", "Denormalized chart of accounts with flow classifications."),
    ("dim_payee", "Dimension", "Payee lookup dimension for analytical slicing."),
    ("dim_source", "Dimension", "Entry provenance dimension (manual, payslip, opening, transfer)."),
    ("fact_ledger_line", "Fact", "Atomic journal-line facts with transfer flags."),
    ("fact_payslip_item", "Fact", "Statutory salary breakdown line items."),
    ("agg_monthly_account", "Rollup", "Pre-aggregated monthly inflows and outflows by account."),
    ("agg_daily_cashflow", "Rollup", "Daily cashflow net changes and cumulative running balance."),
]

ALLOWED_OLTP_NAMES = {t[0] for t in OLTP_TABLES}
ALLOWED_OLAP_NAMES = {t[0] for t in OLAP_TABLES}


def _sqlite_db_path(db: Session) -> Path | None:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return None
    db_name = bind.url.database
    if not db_name or db_name == ":memory:":
        return None
    p = Path(db_name)
    return p.resolve() if p.exists() else None


def _backup_sqlite(db: Session, label: str = "before-reset") -> str | None:
    """Create a verified SQLite backup before a destructive operation."""
    src_path = _sqlite_db_path(db)
    if src_path is None or not src_path.exists():
        return None
    backup_dir = src_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
    dest_path = backup_dir / f"loaf_ledger-{label}-{stamp}.sqlite3"
    with sqlite3.connect(f"{src_path.as_uri()}?mode=ro", uri=True) as source:
        with sqlite3.connect(str(dest_path)) as target:
            source.backup(target)
    return dest_path.name


def _oltp_counts(db: Session) -> dict[str, int]:
    return {
        "users": db.execute(select(func.count()).select_from(User)).scalar_one(),
        "accounts": db.execute(select(func.count()).select_from(Account)).scalar_one(),
        "payees": db.execute(select(func.count()).select_from(Payee)).scalar_one(),
        "journal_entries": db.execute(select(func.count()).select_from(JournalEntry)).scalar_one(),
        "journal_lines": db.execute(select(func.count()).select_from(JournalLine)).scalar_one(),
        "budgets": db.execute(select(func.count()).select_from(Budget)).scalar_one(),
        "fund_overrides": db.execute(select(func.count()).select_from(FundOverride)).scalar_one(),
        "salary_profiles": db.execute(
            select(func.count()).select_from(SalaryProfile)
        ).scalar_one(),
    }


def _olap_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        with cursor() as conn:
            for name, _, _ in OLAP_TABLES:
                row = conn.execute(f"SELECT count(*) FROM {name}").fetchone()
                counts[name] = int(row[0]) if row else 0
    except WarehouseError:
        for name, _, _ in OLAP_TABLES:
            counts[name] = 0
    return counts


@router.get("/database", response_model=DatabaseOverviewOut)
def database_overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Return full OLTP and OLAP table counts, file sizes, and backup status."""
    bind = db.get_bind()
    oltp_path_obj = _sqlite_db_path(db)
    oltp_size = oltp_path_obj.stat().st_size if oltp_path_obj and oltp_path_obj.exists() else None

    wh_path_str = warehouse_path()
    wh_path_obj = Path(wh_path_str).resolve()
    olap_size = wh_path_obj.stat().st_size if wh_path_obj.exists() else None

    backups_count = 0
    latest_backup = None
    if oltp_path_obj:
        backup_dir = oltp_path_obj.parent / "backups"
        if backup_dir.exists():
            files = sorted(backup_dir.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime)
            backups_count = len(files)
            if files:
                latest_backup = files[-1].name

    oltp_c = _oltp_counts(db)
    olap_c = _olap_counts()

    tables: list[TableInfoOut] = []
    for name, role, desc in OLTP_TABLES:
        tables.append(
            TableInfoOut(
                name=name,
                store="oltp",
                role=role,
                row_count=oltp_c.get(name, 0),
                description=desc,
            )
        )
    for name, role, desc in OLAP_TABLES:
        tables.append(
            TableInfoOut(
                name=name,
                store="olap",
                role=role,
                row_count=olap_c.get(name, 0),
                description=desc,
            )
        )

    wh_status = status.check(db, user.id)
    return DatabaseOverviewOut(
        oltp_engine=bind.dialect.name,
        oltp_path=str(oltp_path_obj) if oltp_path_obj else str(bind.url),
        oltp_size_bytes=oltp_size,
        olap_path=str(wh_path_obj),
        olap_size_bytes=olap_size,
        backups_count=backups_count,
        latest_backup=latest_backup,
        tables=tables,
        warehouse_ok=wh_status.ok,
        warehouse_drift=wh_status.drift,
    )


def _serialize_cell(val: object) -> object:
    if val is None or isinstance(val, bool | int | float | str):
        return val
    if isinstance(val, Decimal):
        return f"{val:.2f}"
    if isinstance(val, datetime):
        return val.isoformat(sep=" ", timespec="seconds")
    return str(val)


@router.get("/database/preview/{table_name}", response_model=TablePreviewOut)
def preview_table(
    table_name: str,
    limit: int = Query(20, ge=1, le=100),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Safely preview rows from a whitelisted OLTP or OLAP table."""
    if table_name in ALLOWED_OLTP_NAMES:
        total = db.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one()
        result = db.execute(text(f"SELECT * FROM {table_name} LIMIT :lim"), {"lim": limit})
        cols = list(result.keys())
        rows = [
            {col: _serialize_cell(val) for col, val in zip(cols, r, strict=False)}
            for r in result.fetchall()
        ]
        return TablePreviewOut(
            table=table_name,
            store="oltp",
            columns=cols,
            rows=rows,
            total_rows=int(total),
        )

    if table_name in ALLOWED_OLAP_NAMES:
        try:
            with cursor() as conn:
                total = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
                rel = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", [limit])
                cols = [d[0] for d in rel.description]
                raw_rows = rel.fetchall()
                rows = [
                    {col: _serialize_cell(val) for col, val in zip(cols, r, strict=False)}
                    for r in raw_rows
                ]
                return TablePreviewOut(
                    table=table_name,
                    store="olap",
                    columns=cols,
                    rows=rows,
                    total_rows=int(total),
                )
        except WarehouseError as exc:
            raise HTTPException(503, f"Warehouse unavailable: {exc}") from exc

    raise HTTPException(404, f"Unknown or non-previewable table: {table_name}")


def _restore_clean_baseline(db: Session, user_id: int) -> None:
    """Clear all user financial records and restore the 36 built-in accounts."""
    entry_ids = select(JournalEntry.id).where(JournalEntry.user_id == user_id)
    db.execute(delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids)))
    db.execute(delete(JournalEntry).where(JournalEntry.user_id == user_id))
    db.execute(delete(Budget).where(Budget.user_id == user_id))
    db.execute(delete(FundOverride).where(FundOverride.user_id == user_id))
    db.execute(delete(Payee).where(Payee.user_id == user_id))
    db.execute(delete(SalaryProfile).where(SalaryProfile.user_id == user_id))
    db.execute(delete(Account).where(Account.user_id == user_id))
    db.flush()

    for code, name, type_, subtype, statutory in CHART:
        db.add(
            Account(
                user_id=user_id,
                code=code,
                name=name,
                type=type_,
                subtype=subtype,
                is_statutory=statutory,
                is_system=True,
                is_active=True,
                opening_balance=Decimal("0"),
            )
        )
    db.commit()


@router.post("/reset-baseline", response_model=SystemOperationOut)
def reset_baseline(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Reset the database to the clean 36-account zero-balance baseline."""
    backup_file = _backup_sqlite(db, label="before-reset")
    _restore_clean_baseline(db, user.id)
    try:
        wh_counts = etl.rebuild_all(db)
    except WarehouseError as exc:
        raise HTTPException(503, f"Ledger reset, but warehouse rebuild failed: {exc}") from exc

    counts = _oltp_counts(db)
    return SystemOperationOut(
        action="reset_baseline",
        backup_file=backup_file,
        counts=counts,
        warehouse_counts=wh_counts,
        detail="Reset to 36 built-in zero-balance accounts and rebuilt the warehouse.",
    )


@router.post("/seed-demo", response_model=SystemOperationOut)
def load_demo_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Populate the demo dataset (if the journal is empty) and rebuild the warehouse."""
    seed_demo(db)
    try:
        wh_counts = etl.rebuild_all(db)
    except WarehouseError as exc:
        raise HTTPException(503, f"Demo seeded, but warehouse rebuild failed: {exc}") from exc

    counts = _oltp_counts(db)
    return SystemOperationOut(
        action="seed_demo",
        backup_file=None,
        counts=counts,
        warehouse_counts=wh_counts,
        detail="Loaded demo ledger data and synchronized the DuckDB warehouse.",
    )


@router.post("/delete-data", response_model=SystemOperationOut)
def delete_data(
    payload: DataDeletionRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Delete targeted financial data categories and synchronize the warehouse."""
    backup_file = _backup_sqlite(db, label=f"before-delete-{payload.target}")
    target = payload.target

    if target == "entries":
        entry_ids = select(JournalEntry.id).where(JournalEntry.user_id == user.id)
        db.execute(delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids)))
        db.execute(delete(JournalEntry).where(JournalEntry.user_id == user.id))
        db.commit()
        detail = "Deleted all journal entries and lines."
    elif target == "budgets":
        db.execute(delete(Budget).where(Budget.user_id == user.id))
        db.execute(delete(FundOverride).where(FundOverride.user_id == user.id))
        db.commit()
        detail = "Deleted all monthly budgets and starting-fund overrides."
    elif target == "salary_profiles":
        db.execute(delete(SalaryProfile).where(SalaryProfile.user_id == user.id))
        db.commit()
        detail = "Deleted all saved salary profiles."
    elif target == "custom_accounts_payees":
        # Unlink payees from existing entries before deleting payees
        db.execute(
            update(JournalEntry).where(JournalEntry.user_id == user.id).values(payee_id=None)
        )
        db.execute(delete(Payee).where(Payee.user_id == user.id))
        # Delete custom accounts that have no postings/budgets; archive any that do
        used_in_lines = set(db.execute(select(JournalLine.account_id).distinct()).scalars().all())
        used_in_budgets = set(db.execute(select(Budget.account_id).distinct()).scalars().all())
        used_ids = used_in_lines | used_in_budgets
        custom_accounts = (
            db.execute(
                select(Account).where(Account.user_id == user.id, Account.is_system.is_(False))
            )
            .scalars()
            .all()
        )
        for acc in custom_accounts:
            if acc.id in used_ids:
                acc.is_active = False
                acc.archived_at = datetime.utcnow()
            else:
                db.delete(acc)
        db.commit()
        detail = "Removed payees and unused custom accounts (archived custom accounts in use)."
    elif target == "all_financial":
        _restore_clean_baseline(db, user.id)
        detail = "Deleted all financial records and restored the 36 built-in accounts."

    try:
        wh_counts = etl.rebuild_all(db)
    except WarehouseError as exc:
        raise HTTPException(503, f"Data deleted, but warehouse rebuild failed: {exc}") from exc

    counts = _oltp_counts(db)
    return SystemOperationOut(
        action=f"delete_{target}",
        backup_file=backup_file,
        counts=counts,
        warehouse_counts=wh_counts,
        detail=detail,
    )
