"""Payees / merchants — an optional dimension on an entry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.payee import Payee
from app.models.user import User
from app.schemas import PayeeCreate, PayeeOut

router = APIRouter(prefix="/payees", tags=["payees"])


@router.get("", response_model=list[PayeeOut])
def list_payees(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return (
        db.execute(select(Payee).where(Payee.user_id == user.id).order_by(Payee.name))
        .scalars()
        .all()
    )


@router.post("", response_model=PayeeOut, status_code=201)
def create_payee(
    payload: PayeeCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    payee = Payee(
        user_id=user.id, name=payload.name, default_account_id=payload.default_account_id
    )
    db.add(payee)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"Payee {payload.name!r} already exists") from exc
    db.refresh(payee)
    return payee
