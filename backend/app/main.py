"""Loaf & Ledger API — FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    accounts,
    analytics,
    budgets,
    dashboard,
    export,
    ledger,
    meta,
    payees,
    salary,
    warehouse,
)

settings = get_settings()
log = logging.getLogger(__name__)

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open (and initialize) the warehouse eagerly.

    Doing it at boot rather than on the first analytics request means a missing
    or locked DuckDB file surfaces in the startup log, not mid-request.
    """
    from app.warehouse.engine import WarehouseError, connect

    try:
        connect()
    except WarehouseError:
        log.exception("Warehouse unavailable at startup; analytics will report stale")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Loaf & Ledger API",
        version=VERSION,
        description=(
            "Personal finance as a double-entry ledger (OLTP) with a DuckDB "
            "star-schema warehouse (OLAP) behind the analytics."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix
    for module in (
        meta,
        accounts,
        payees,
        salary,
        ledger,
        analytics,
        budgets,
        export,
        dashboard,
        warehouse,
    ):
        app.include_router(module.router, prefix=prefix)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": VERSION}

    return app


app = create_app()
