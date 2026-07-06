"""Live currency-rate trend for the dashboard (item: '01 Dashboard' FX chart)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models.user import User
from app.schemas import FxRatePoint, FxRatesResponse
from app.services import fx_live

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates", response_model=FxRatesResponse)
def rates(
    base: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    result = fx_live.refresh(db, base or user.base_currency, start=start, end=end)
    return FxRatesResponse(
        base=result.base,
        quotes=result.quotes,
        live=result.live,
        as_of=result.as_of,
        series=[FxRatePoint(date=p["date"], rates=p["rates"]) for p in result.series],
    )
