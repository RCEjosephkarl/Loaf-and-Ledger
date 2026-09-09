"""Shared FastAPI dependencies."""

from __future__ import annotations

from datetime import date

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.services.user import get_single_user


def current_user(db: Session = Depends(get_db)) -> User:
    """The single local user (created on first access)."""
    return get_single_user(db)


class Filters:
    """Global dashboard filters (F6): time range and account.

    Currency and region are gone — the app is single-currency (PHP) and
    single-jurisdiction (PH), so account is the dimension worth slicing on.
    """

    def __init__(
        self,
        start: date | None = None,
        end: date | None = None,
        account_id: int | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.account_id = account_id
