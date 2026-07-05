"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLite by default so the app runs with zero setup; Postgres in production.
    database_url: str = "sqlite:///./loaf_ledger.db"
    frontend_origin: str = "http://localhost:5173"

    # Local single-user deployment: no multi-user auth. An optional app password
    # can gate the whole instance later without a schema change (see APP_PASSWORD).
    app_password: str = ""

    api_prefix: str = "/api/v1"
    # The single tax year modelled in v1 (schema still carries a per-row year).
    default_tax_year: int = 2025


@lru_cache
def get_settings() -> Settings:
    return Settings()
