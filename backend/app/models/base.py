"""Declarative base, shared column types, and domain enums."""

from __future__ import annotations

import enum

from sqlalchemy import JSON, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# JSONB in Postgres (indexable, typed), plain JSON in SQLite dev — one column type.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")

# Two-decimal fixed money, returned as Decimal on every backend.
Money = Numeric(14, 2, asdecimal=True)

# Exchange rate: higher precision than money.
Rate = Numeric(18, 8, asdecimal=True)


class Base(DeclarativeBase):
    pass


class Region(str, enum.Enum):
    """Salary/tax region. EU is modelled at national level via Germany in v1."""

    PH = "PH"
    US = "US"
    AU = "AU"
    EU = "EU"


class TxDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class BudgetScope(str, enum.Enum):
    """Period granularity for budget status/fund views."""

    MONTH = "month"
    QUARTER = "3m"
    YTD = "ytd"
    ALL = "all"


# Canonical display currency per region (amounts are stored in native currency).
REGION_CURRENCY: dict[Region, str] = {
    Region.PH: "PHP",
    Region.US: "USD",
    Region.AU: "AUD",
    Region.EU: "EUR",
}
