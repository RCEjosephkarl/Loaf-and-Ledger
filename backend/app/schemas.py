"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.base import AccountType, BudgetScope, EntrySource, FlowClass
from app.models.salary import PayPeriod

# ---------------------------------------------------------------- meta / user


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str | None
    currency: str = "PHP"


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None


# ---------------------------------------------------------------- accounts


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    type: AccountType
    subtype: str | None
    is_statutory: bool
    is_system: bool
    is_active: bool
    opening_balance: Decimal
    archived_at: datetime | None


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1, max_length=80)
    type: AccountType
    subtype: str | None = None
    opening_balance: Decimal = Decimal("0")


class AccountUpdate(BaseModel):
    name: str | None = None
    subtype: str | None = None
    is_active: bool | None = None


class AccountBalanceOut(BaseModel):
    account_id: int
    code: str
    name: str
    type: AccountType
    subtype: str | None
    is_active: bool
    debits: Decimal
    credits: Decimal
    balance: Decimal


class AccountBalancesResponse(BaseModel):
    currency: str
    as_of: datetime | None
    accounts: list[AccountBalanceOut]
    #: Net balance per account type, in each type's normal-balance direction.
    totals_by_type: dict[str, Decimal]
    net_worth: Decimal


# ---------------------------------------------------------------- payees


class PayeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    default_account_id: int | None


class PayeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_account_id: int | None = None


# ---------------------------------------------------------------- journal


class JournalLineIn(BaseModel):
    account_id: int
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    memo: str | None = None

    @model_validator(mode="after")
    def one_side_only(self) -> JournalLineIn:
        if self.debit and self.credit:
            raise ValueError("A line is either a debit or a credit, not both")
        if not self.debit and not self.credit:
            raise ValueError("A line must carry an amount")
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Amounts cannot be negative")
        return self


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    line_no: int
    account_id: int
    debit: Decimal
    credit: Decimal
    memo: str | None


class JournalEntryCreate(BaseModel):
    occurred_at: datetime
    lines: list[JournalLineIn] = Field(min_length=2)
    memo: str | None = None
    payee_id: int | None = None


class SimpleEntryCreate(BaseModel):
    """The quick-entry form: money in, money out, or a transfer.

    `account_id` is always the balance-sheet side — where the money landed, or
    where it came from. `counter_account_id` is the income or expense account
    (or the other asset/liability account, for a transfer).
    """

    kind: str = Field(pattern="^(income|expense|transfer)$")
    amount: Decimal = Field(gt=0)
    account_id: int
    counter_account_id: int
    occurred_at: datetime
    memo: str | None = None
    payee_id: int | None = None


class JournalEntryUpdate(BaseModel):
    occurred_at: datetime | None = None
    lines: list[JournalLineIn] | None = None
    memo: str | None = None
    payee_id: int | None = None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    memo: str | None
    payee_id: int | None
    source: EntrySource
    source_ref: str | None
    voided_at: datetime | None
    lines: list[JournalLineOut]


# ---------------------------------------------------------------- F1 salary


class SalaryCalcRequest(BaseModel):
    gross_amount: Decimal = Field(gt=0)
    pay_period: PayPeriod = PayPeriod.MONTHLY
    tax_year: int | None = None


class SalaryLineItem(BaseModel):
    key: str
    label: str
    amount: Decimal
    amount_period: Decimal
    kind: str


class SalaryBreakdown(BaseModel):
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
    gross_amount: Decimal = Field(gt=0)
    pay_period: PayPeriod = PayPeriod.MONTHLY
    tax_year: int | None = None
    make_active: bool = True


class SalaryProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    gross_amount: Decimal
    pay_period: PayPeriod
    tax_year: int
    net_amount: Decimal
    total_deductions: Decimal
    breakdown: dict
    is_active: bool


class PayslipPostRequest(BaseModel):
    deposit_account_id: int
    occurred_at: datetime | None = None


class PayslipPostResponse(BaseModel):
    entry: JournalEntryOut
    created: bool


# ---------------------------------------------------------------- F4 budgets


class BudgetCreate(BaseModel):
    account_id: int
    year: int
    month: int = Field(ge=1, le=12)
    limit_amount: Decimal = Field(gt=0)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    year: int
    month: int
    limit_amount: Decimal


class BudgetStatus(BaseModel):
    account_id: int
    account_name: str
    account_code: str
    year: int | None = None  # populated for scope=month, else None
    month: int | None = None
    scope: str = "month"
    period_start: date
    period_end: date  # inclusive
    limit_amount: Decimal
    spent: Decimal
    remaining: Decimal
    utilization: Decimal
    over_budget: bool


class FundOverrideIn(BaseModel):
    scope: BudgetScope
    anchor: date | None = None
    amount: Decimal


class FundStatus(BaseModel):
    scope: BudgetScope
    period_start: date
    period_end: date  # inclusive
    amount: Decimal
    is_override: bool


# ---------------------------------------------------------------- analytics


class AccountTotal(BaseModel):
    account_id: int
    code: str
    account_name: str
    type: AccountType
    flow_class: FlowClass
    is_statutory: bool
    total: Decimal
    entries: int


class Insight(BaseModel):
    key: str
    severity: str  # info | warning | good
    title: str
    detail: str


class AnalyticsOverview(BaseModel):
    currency: str
    total_income: Decimal
    total_expense: Decimal
    net_cashflow: Decimal
    transfer_volume: Decimal
    salary_net_period: Decimal | None
    salary_deduction_rate: Decimal | None
    savings_rate: Decimal
    accounts: list[AccountTotal]


class MonthlyPoint(BaseModel):
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal


class MonthlyResponse(BaseModel):
    currency: str
    series: list[MonthlyPoint]


class MonthlyAccountSeries(BaseModel):
    account_id: int
    account_name: str
    values: list[Decimal]


class MonthlyByAccountResponse(BaseModel):
    currency: str
    months: list[str]  # "YYYY-MM", oldest -> newest
    series: list[MonthlyAccountSeries]


class RunningBalancePoint(BaseModel):
    date: date
    income: Decimal
    expense: Decimal
    net: Decimal
    balance: Decimal
    cumulative_balance: Decimal


class RunningBalanceResponse(BaseModel):
    currency: str
    points: list[RunningBalancePoint]


class EarningsItem(BaseModel):
    key: str
    label: str
    kind: str
    amount: Decimal
    amount_annual: Decimal


class EarningsResponse(BaseModel):
    currency: str
    profile_id: int | None
    tax_year: int | None
    pay_period: str | None
    gross: Decimal
    net: Decimal
    total_deductions: Decimal
    take_home_rate: Decimal
    items: list[EarningsItem]


class DashboardSummary(BaseModel):
    currency: str
    total_income: Decimal
    total_expense: Decimal
    net_cashflow: Decimal
    transfer_volume: Decimal
    salary_net_period: Decimal | None
    savings_rate: Decimal
    net_worth: Decimal
    top_expense_accounts: list[AccountTotal]
    insights: list[Insight]


# ---------------------------------------------------------------- warehouse


class WarehouseStatusOut(BaseModel):
    ok: bool
    is_stale: bool
    last_loaded_at: datetime | None
    oltp_lines: int
    olap_lines: int
    drift: int
    integrity_problems: list[dict]
    note: str | None
    warehouse_path: str


class WarehouseRebuildOut(BaseModel):
    counts: dict[str, int]
