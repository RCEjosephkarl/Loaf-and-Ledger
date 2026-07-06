"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import BudgetScope, Region, TxDirection
from app.models.salary import PayPeriod

# ---------------------------------------------------------------- meta / user


class RegionInfo(BaseModel):
    region: Region
    name: str
    currency: str
    modelled_as: str
    supported: bool


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str | None
    base_currency: str
    default_region: Region


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    base_currency: str | None = None
    default_region: Region | None = None


# ---------------------------------------------------------------- F1 salary


class SalaryCalcRequest(BaseModel):
    region: Region
    gross_amount: Decimal = Field(gt=0)
    pay_period: PayPeriod = PayPeriod.MONTHLY
    tax_year: int | None = None


class SalaryLineItem(BaseModel):
    key: str
    label: str
    amount: Decimal
    kind: str


class SalaryBreakdown(BaseModel):
    region: str
    currency: str
    tax_year: int
    pay_period: str
    gross_annual: Decimal
    net_annual: Decimal
    gross_period: Decimal
    net_period: Decimal
    total_tax: Decimal
    total_social: Decimal
    total_deductions: Decimal
    effective_rate: Decimal
    items: list[SalaryLineItem]


class SalaryProfileCreate(BaseModel):
    label: str = "My salary"
    region: Region
    gross_amount: Decimal = Field(gt=0)
    pay_period: PayPeriod = PayPeriod.MONTHLY
    tax_year: int | None = None
    make_active: bool = True


class SalaryProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    region: Region
    currency: str
    gross_amount: Decimal
    pay_period: PayPeriod
    tax_year: int
    net_amount: Decimal
    total_deductions: Decimal
    breakdown: dict
    is_active: bool


# ---------------------------------------------------------------- categories


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    direction: TxDirection
    statutory: bool
    region: Region | None
    is_system: bool


class CategoryCreate(BaseModel):
    name: str
    direction: TxDirection


# ---------------------------------------------------------------- F2 ledger


class TransactionCreate(BaseModel):
    direction: TxDirection
    category_id: int
    amount: Decimal = Field(gt=0)
    currency: str | None = None  # defaults to region/base currency if omitted
    region: Region | None = None
    occurred_on: date
    occurred_time: time | None = None
    description: str | None = None


class TransactionUpdate(BaseModel):
    category_id: int | None = None
    amount: Decimal | None = None
    currency: str | None = None
    occurred_on: date | None = None
    occurred_time: time | None = None
    description: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    direction: TxDirection
    category_id: int
    amount: Decimal
    currency: str
    region: Region | None
    occurred_on: date
    occurred_time: time | None
    description: str | None


class TransactionBalancesResponse(BaseModel):
    currency: str
    balances: dict[int, Decimal]


# ---------------------------------------------------------------- F4 budgets


class BudgetCreate(BaseModel):
    category_id: int
    year: int
    month: int = Field(ge=1, le=12)
    limit_amount: Decimal = Field(gt=0)
    currency: str | None = None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    year: int
    month: int
    limit_amount: Decimal
    currency: str


class BudgetStatus(BaseModel):
    category_id: int
    category_name: str
    year: int | None = None  # populated for scope=month, else None
    month: int | None = None
    scope: str = "month"
    period_start: date
    period_end: date  # inclusive
    limit_amount: Decimal
    spent: Decimal
    remaining: Decimal
    utilization: Decimal
    currency: str
    over_budget: bool


class FundOverrideIn(BaseModel):
    scope: BudgetScope
    anchor: date | None = None
    amount: Decimal
    currency: str | None = None


class FundStatus(BaseModel):
    scope: BudgetScope
    period_start: date
    period_end: date  # inclusive
    amount: Decimal
    currency: str
    is_override: bool


# ---------------------------------------------------------------- F3/F6 analytics


class CategoryTotal(BaseModel):
    category_id: int | None
    category_name: str
    direction: TxDirection
    total: Decimal


class Insight(BaseModel):
    key: str
    severity: str  # info | warning | good
    title: str
    detail: str


class MonthlyCategorySeries(BaseModel):
    category_id: int | None
    category_name: str
    values: list[Decimal]


class MonthlyByCategoryResponse(BaseModel):
    currency: str
    months: list[str]  # "YYYY-MM", oldest -> newest
    series: list[MonthlyCategorySeries]


class DashboardSummary(BaseModel):
    currency: str
    region: Region | None
    total_income: Decimal
    total_expense: Decimal
    net_cashflow: Decimal
    salary_net_period: Decimal | None
    savings_rate: Decimal
    top_expense_categories: list[CategoryTotal]
    insights: list[Insight]


# ---------------------------------------------------------------- FX rates (live)


class FxRatePoint(BaseModel):
    date: date
    rates: dict[str, Decimal]


class FxRatesResponse(BaseModel):
    base: str
    quotes: list[str]
    live: bool
    as_of: date | None
    series: list[FxRatePoint]


# ---------------------------------------------------------------- running balance


class RunningBalancePoint(BaseModel):
    date: date
    income: Decimal
    expense: Decimal
    net: Decimal
    balance: Decimal


class RunningBalanceResponse(BaseModel):
    currency: str
    points: list[RunningBalancePoint]
