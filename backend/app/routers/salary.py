"""F1 — salary calculator: ephemeral compute, persistent profiles, and the
posting that turns a payslip into ledger entries."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.models.salary import SalaryProfile
from app.models.user import User
from app.schemas import (
    PayslipPostRequest,
    PayslipPostResponse,
    SalaryBreakdown,
    SalaryCalcRequest,
    SalaryProfileCreate,
    SalaryProfileOut,
)
from app.services import journal as journal_svc
from app.services import payslip as payslip_svc
from app.tax import engine
from app.warehouse import etl

router = APIRouter(prefix="/salary", tags=["salary"])
settings = get_settings()


def _compute(gross: Decimal, pay_period, tax_year: int | None):  # noqa: ANN001
    return engine.compute(
        gross, pay_period=pay_period.value, year=tax_year or settings.default_tax_year
    )


@router.post("/calculate", response_model=SalaryBreakdown)
def calculate(payload: SalaryCalcRequest) -> dict:
    """Compute a net-vs-deducted breakdown without persisting (live calculator)."""
    return _compute(payload.gross_amount, payload.pay_period, payload.tax_year).to_dict()


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
    breakdown = _compute(payload.gross_amount, payload.pay_period, payload.tax_year)
    year = payload.tax_year or settings.default_tax_year

    if payload.make_active:
        for p in _active_profiles(db, user.id):
            p.is_active = False

    profile = SalaryProfile(
        user_id=user.id,
        label=payload.label,
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
    etl.safe_apply_payslip(db, profile.id)
    return profile


@router.post("/profiles/{profile_id}/activate", response_model=SalaryProfileOut)
def activate_profile(
    profile_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = _owned(db, user, profile_id)
    for p in _active_profiles(db, user.id):
        p.is_active = False
    profile.is_active = True
    db.commit()
    db.refresh(profile)
    # The `is_active` flag is a dimension attribute on fact_payslip_item, so
    # both the old and new active profiles need reloading.
    for p in db.execute(
        select(SalaryProfile).where(SalaryProfile.user_id == user.id)
    ).scalars():
        etl.safe_apply_payslip(db, p.id)
    return profile


@router.post("/profiles/{profile_id}/post", response_model=PayslipPostResponse)
def post_to_ledger(
    profile_id: int,
    payload: PayslipPostRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Post this payslip to the ledger as one balanced multi-line entry.

    Idempotent: a profile posts at most once, enforced by the unique
    (user, source, source_ref) constraint on journal_entries.
    """
    profile = _owned(db, user, profile_id)
    try:
        entry, created = payslip_svc.post_payslip(
            db,
            user.id,
            profile,
            deposit_account_id=payload.deposit_account_id,
            occurred_at=payload.occurred_at,
        )
    except journal_svc.JournalError as exc:
        raise HTTPException(422, str(exc)) from exc
    if created:
        etl.safe_apply_entry(db, entry.id)
    return PayslipPostResponse(entry=entry, created=created)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = _owned(db, user, profile_id)
    db.delete(profile)
    db.commit()
    etl.safe_apply_payslip(db, profile_id)


def _owned(db: Session, user: User, profile_id: int) -> SalaryProfile:
    profile = db.get(SalaryProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(404, "Salary profile not found")
    return profile


def _active_profiles(db: Session, user_id: int):
    return (
        db.execute(
            select(SalaryProfile).where(
                SalaryProfile.user_id == user_id, SalaryProfile.is_active.is_(True)
            )
        )
        .scalars()
        .all()
    )
