"""Drift detection between the two stores.

Write-through can miss — a locked file, a crash between the ledger commit and
the warehouse write. Rather than hoping it does not, the app compares the two
stores on demand and says plainly when analytics are behind the ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.journal import JournalEntry, JournalLine
from app.services.journal import integrity_check
from app.warehouse.engine import WarehouseError, cursor


@dataclass
class WarehouseStatus:
    ok: bool
    is_stale: bool
    last_loaded_at: datetime | None
    oltp_lines: int
    olap_lines: int
    drift: int
    integrity_problems: list[dict]
    note: str | None
    warehouse_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def check(db: Session, user_id: int) -> WarehouseStatus:
    from app.warehouse.engine import warehouse_path

    oltp_lines = db.execute(
        select(func.count())
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.user_id == user_id, JournalEntry.voided_at.is_(None))
    ).scalar_one()

    problems = [
        {"entry_id": p.entry_id, "kind": p.kind, "detail": p.detail}
        for p in integrity_check(db, user_id)
    ]

    try:
        with cursor() as conn:
            olap_lines = conn.execute("SELECT count(*) FROM fact_ledger_line").fetchone()[0]
            row = conn.execute(
                "SELECT last_loaded_at, is_stale, note FROM etl_watermark "
                "WHERE table_name = 'fact_ledger_line'"
            ).fetchone()
    except WarehouseError as exc:
        return WarehouseStatus(
            ok=False,
            is_stale=True,
            last_loaded_at=None,
            oltp_lines=oltp_lines,
            olap_lines=0,
            drift=oltp_lines,
            integrity_problems=problems,
            note=str(exc),
            warehouse_path=warehouse_path(),
        )

    last_loaded_at, is_stale, note = row if row else (None, False, None)
    drift = oltp_lines - olap_lines
    return WarehouseStatus(
        ok=drift == 0 and not is_stale and not problems,
        is_stale=bool(is_stale) or drift != 0,
        last_loaded_at=last_loaded_at,
        oltp_lines=oltp_lines,
        olap_lines=olap_lines,
        drift=drift,
        integrity_problems=problems,
        note=note,
        warehouse_path=warehouse_path(),
    )
