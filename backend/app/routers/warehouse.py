"""OLAP warehouse operations: drift status and full rebuild."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.user import User
from app.schemas import WarehouseRebuildOut, WarehouseStatusOut
from app.warehouse import etl, status
from app.warehouse.engine import WarehouseError

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("/status", response_model=WarehouseStatusOut)
def warehouse_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Compare the two stores and report any drift.

    `drift` is the OLTP line count minus the OLAP fact count; anything other
    than zero means write-through missed something and a rebuild is due.
    """
    return WarehouseStatusOut(**status.check(db, user.id).to_dict())


@router.post("/rebuild", response_model=WarehouseRebuildOut)
def rebuild(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Full truncate-and-reload, in-process.

    The CLI (`python -m app.warehouse.rebuild`) does the same thing, but cannot
    run while this server holds the DuckDB file — so this endpoint is the way
    to rebuild without downtime.
    """
    try:
        counts = etl.rebuild_all(db)
    except WarehouseError as exc:
        raise HTTPException(503, f"Rebuild failed: {exc}") from exc
    return WarehouseRebuildOut(counts=counts)
