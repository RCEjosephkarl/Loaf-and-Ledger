"""Reference table of supported tax jurisdictions (national-level in v1)."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Region


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[Region] = mapped_column(Enum(Region), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    # National-level jurisdiction that backs this region's rules in v1
    # (e.g. EU is modelled via Germany). Sub-national scope can be added later.
    modelled_as: Mapped[str] = mapped_column(String(120))
    supported: Mapped[bool] = mapped_column(Boolean, default=True)
