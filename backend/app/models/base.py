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

# The app is single-currency (see README §2). Amounts carry no currency column;
# this constant is the one place the code names the currency, leaving a seam for
# reintroducing multi-currency as a deliberate feature rather than a default.
CURRENCY = "PHP"


class Base(DeclarativeBase):
    pass


class AccountType(str, enum.Enum):
    """The five classical account types. `normal_balance` follows from this:
    assets and expenses increase on the debit side, everything else on credit."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


#: Account types whose balance increases with a debit.
DEBIT_NORMAL = frozenset({AccountType.ASSET, AccountType.EXPENSE})


def normal_balance(account_type: AccountType) -> str:
    return "dr" if account_type in DEBIT_NORMAL else "cr"


class FlowClass(str, enum.Enum):
    """How an account participates in cash-flow analytics.

    Income is money arriving, expense is money leaving; asset/liability/equity
    accounts are stocks, not flows — a movement between two of them is a
    transfer and must never be counted as earning or spending.
    """

    INFLOW = "inflow"
    OUTFLOW = "outflow"
    BALANCE = "balance"


def flow_class(account_type: AccountType) -> FlowClass:
    if account_type is AccountType.INCOME:
        return FlowClass.INFLOW
    if account_type is AccountType.EXPENSE:
        return FlowClass.OUTFLOW
    return FlowClass.BALANCE


class EntrySource(str, enum.Enum):
    """Where a journal entry came from — a dimension in the warehouse, and the
    hook that makes payslip postings idempotent (see services/payslip.py)."""

    MANUAL = "manual"
    PAYSLIP = "payslip"
    OPENING = "opening"
    TRANSFER = "transfer"
    IMPORT = "import"


class BudgetScope(str, enum.Enum):
    """Period granularity for budget status/fund views."""

    MONTH = "month"
    QUARTER = "3m"
    YTD = "ytd"
    ALL = "all"
