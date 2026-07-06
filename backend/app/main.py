"""Loaf & Ledger API — FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analytics, budgets, dashboard, export, fx, ledger, meta, salary

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Loaf & Ledger API",
        version="0.0.0",
        description="Personal finance with regional salary/tax rules and rule-based insights.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix
    for module in (meta, salary, ledger, analytics, budgets, export, dashboard, fx):
        app.include_router(module.router, prefix=prefix)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": "0.0.0"}

    return app


app = create_app()
