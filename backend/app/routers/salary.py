"""F1 — salary calculator: ephemeral compute + persistent profiles."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models.base import REGION_CURRENCY
from app.models.salary import SalaryProfile
from app.models.user import User
from app.schemas import (
    SalaryBreakdown,
    SalaryCalcRequest,
    SalaryProfileCreate,
    SalaryProfileOut,
)
from app.tax import engine

router = APIRouter(prefix="/salary", tags=["salary"])
settings = get_settings()


def _compute(req_region, gross: Decimal, pay_period, tax_year: int | None):
    year = tax_year or settings.default_tax_year
    return engine.compute(gross, req_region, pay_period=pay_period.value, year=year)


@router.post("/calculate", response_model=SalaryBreakdown)
def calculate(payload: SalaryCalcRequest) -> dict:
    """Compute a net-vs-deducted breakdown without persisting (live calculator)."""
    breakdown = _compute(payload.region, payload.gross_amount, payload.pay_period, payload.tax_year)
    return breakdown.to_dict()


@router.get("/profiles", response_model=list[SalaryProfileOut])
def list_profiles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return (
        db.execute(
            select(SalaryProfile).where(SalaryProfile.user_id == user.id).order_by(SalaryProfile.id)
        )
        .scalars()
        .all()
    )


@router.get("/profiles/active", response_model=SalaryProfileOut | None)
def active_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return (
        db.execute(
            select(SalaryProfile)
            .where(SalaryProfile.user_id == user.id, SalaryProfile.is_active.is_(True))
            .order_by(SalaryProfile.updated_at.desc())
        )
        .scalars()
        .first()
    )


@router.post("/profiles", response_model=SalaryProfileOut, status_code=201)
def create_profile(
    payload: SalaryProfileCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Persist the calculator input plus its computed breakdown snapshot."""
    breakdown = _compute(payload.region, payload.gross_amount, payload.pay_period, payload.tax_year)
    year = payload.tax_year or settings.default_tax_year

    if payload.make_active:
        for p in (
            db.execute(
                select(SalaryProfile).where(
                    SalaryProfile.user_id == user.id, SalaryProfile.is_active.is_(True)
                )
            )
            .scalars()
            .all()
        ):
            p.is_active = False

    profile = SalaryProfile(
        user_id=user.id,
        label=payload.label,
        region=payload.region,
        currency=REGION_CURRENCY[payload.region],
        gross_amount=payload.gross_amount,
        pay_period=payload.pay_period,
        tax_year=year,
        net_amount=breakdown.net_annual,
        total_deductions=breakdown.total_deductions,
        breakdown=breakdown.to_dict(),
        is_active=payload.make_active,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/profiles/{profile_id}/activate", response_model=SalaryProfileOut)
def activate_profile(
    profile_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = db.get(SalaryProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(404, "Salary profile not found")
    for p in (
        db.execute(
            select(SalaryProfile).where(
                SalaryProfile.user_id == user.id, SalaryProfile.is_active.is_(True)
            )
        )
        .scalars()
        .all()
    ):
        p.is_active = False
    profile.is_active = True
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = db.get(SalaryProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(404, "Salary profile not found")
    db.delete(profile)
    db.commit()
