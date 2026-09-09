"""Reference data: the single-user profile and the app's fixed jurisdiction."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import CURRENCY
from app.models.user import User
from app.schemas import UserOut, UserUpdate
from app.tax import engine

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta() -> dict:
    """What this instance is configured for.

    v1 is single-currency and single-jurisdiction; the tax registry still
    reports which regime is modelled so the UI never hard-codes "Philippines".
    """
    rule = engine.get_rule()
    return {
        "currency": CURRENCY,
        "jurisdiction": rule.key,
        "modelled_as": rule.modelled_as,
        "tax_year": engine.DEFAULT_YEAR,
    }


@router.get("/user", response_model=UserOut)
def get_user(user: User = Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, currency=CURRENCY)


@router.patch("/user", response_model=UserOut)
def update_user(
    payload: UserUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, name=user.name, email=user.email, currency=CURRENCY)
