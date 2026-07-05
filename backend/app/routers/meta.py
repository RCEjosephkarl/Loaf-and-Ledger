"""Reference data: supported regions and the single-user profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.base import REGION_CURRENCY
from app.models.jurisdiction import Jurisdiction
from app.models.user import User
from app.schemas import RegionInfo, UserOut, UserUpdate
from app.tax import engine

router = APIRouter(tags=["meta"])


@router.get("/regions", response_model=list[RegionInfo])
def list_regions(db: Session = Depends(get_db)) -> list[RegionInfo]:
    rows = {j.region: j for j in db.execute(select(Jurisdiction)).scalars().all()}
    out: list[RegionInfo] = []
    for region in engine.supported_regions():
        rule = engine.get_rule(region)
        j = rows.get(region)
        out.append(
            RegionInfo(
                region=region,
                name=j.name if j else region.value,
                currency=REGION_CURRENCY[region],
                modelled_as=rule.modelled_as,
                supported=True,
            )
        )
    return out


@router.get("/user", response_model=UserOut)
def get_user(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/user", response_model=UserOut)
def update_user(
    payload: UserUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> User:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
