export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";
export type FlowClass = "inflow" | "outflow" | "balance";
export type EntrySource = "manual" | "payslip" | "opening" | "transfer" | "import";
export type PayPeriod = "monthly" | "annual";
export type BudgetScope = "month" | "3m" | "ytd" | "all";
/** What the quick-entry form posts. The full journal grid posts lines directly. */
export type EntryKind = "income" | "expense" | "transfer";

export interface Meta {
  currency: string;
  jurisdiction: string;
  modelled_as: string;
  tax_year: number;
}

export interface User {
  id: number;
  name: string;
  email: string | null;
  currency: string;
}

// ---------------------------------------------------------------- accounts

export interface Account {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  subtype: string | null;
  is_statutory: boolean;
  is_system: boolean;
  is_active: boolean;
  opening_balance: string;
  archived_at: string | null;
}

export interface AccountBalance {
  account_id: number;
  code: string;
  name: string;
  type: AccountType;
  subtype: string | null;
  is_active: boolean;
  debits: string;
  credits: string;
  balance: string;
}

export interface AccountBalances {
  currency: string;
  as_of: string | null;
  accounts: AccountBalance[];
  totals_by_type: Record<string, string>;
  net_worth: string;
}

export interface Payee {
  id: number;
  name: string;
  default_account_id: number | null;
}

// ---------------------------------------------------------------- journal

export interface JournalLine {
  id: number;
  line_no: number;
  account_id: number;
  debit: string;
  credit: string;
  memo: string | null;
}

export interface JournalEntry {
  id: number;
  occurred_at: string;
  memo: string | null;
  payee_id: number | null;
  source: EntrySource;
  source_ref: string | null;
  voided_at: string | null;
  lines: JournalLine[];
}

export interface JournalLineInput {
  account_id: number;
  debit?: string;
  credit?: string;
  memo?: string;
}

// ---------------------------------------------------------------- salary

export interface LineItem {
  key: string;
  label: string;
  amount: string;
  amount_period: string;
  kind: "gross" | "tax" | "social" | "net" | "info";
}

export interface Breakdown {
  tax_year: number;
  pay_period: string;
  gross_annual: string;
  net_annual: string;
  gross_period: string;
  net_period: string;
  total_tax: string;
  total_social: string;
  total_deductions: string;
  effective_rate: string;
  items: LineItem[];
}

export interface SalaryProfile {
  id: number;
  label: string;
  gross_amount: string;
  pay_period: PayPeriod;
  tax_year: number;
  net_amount: string;
  total_deductions: string;
  breakdown: Breakdown;
  is_active: boolean;
}

// ---------------------------------------------------------------- analytics

export interface AccountTotal {
  account_id: number;
  code: string;
  account_name: string;
  type: AccountType;
  flow_class: FlowClass;
  is_statutory: boolean;
  total: string;
  entries: number;
}

export interface Insight {
  key: string;
  severity: "info" | "warning" | "good";
  title: string;
  detail: string;
}

export interface AnalyticsOverview {
  currency: string;
  total_income: string;
  total_expense: string;
  net_cashflow: string;
  transfer_volume: string;
  salary_net_period: string | null;
  salary_deduction_rate: string | null;
  savings_rate: string;
  accounts: AccountTotal[];
}

export interface DashboardSummary {
  currency: string;
  total_income: string;
  total_expense: string;
  net_cashflow: string;
  transfer_volume: string;
  salary_net_period: string | null;
  savings_rate: string;
  net_worth: string;
  top_expense_accounts: AccountTotal[];
  insights: Insight[];
}

export interface MonthlyPoint {
  month: string;
  income: string;
  expense: string;
  net: string;
}

export interface MonthlyAccountSeries {
  account_id: number;
  account_name: string;
  values: string[];
}

export interface MonthlyByAccountResponse {
  currency: string;
  months: string[];
  series: MonthlyAccountSeries[];
}

export interface RunningBalancePoint {
  date: string;
  income: string;
  expense: string;
  net: string;
  balance: string;
  cumulative_balance: string;
}

export interface RunningBalanceResponse {
  currency: string;
  points: RunningBalancePoint[];
}

export interface EarningsItem {
  key: string;
  label: string;
  kind: "gross" | "tax" | "social" | "net" | "info";
  amount: string;
  amount_annual: string;
}

export interface EarningsResponse {
  currency: string;
  profile_id: number | null;
  tax_year: number | null;
  pay_period: string | null;
  gross: string;
  net: string;
  total_deductions: string;
  take_home_rate: string;
  items: EarningsItem[];
}

// ---------------------------------------------------------------- budgets

export interface Budget {
  id: number;
  account_id: number;
  year: number;
  month: number;
  limit_amount: string;
}

export interface BudgetStatus {
  account_id: number;
  account_name: string;
  account_code: string;
  year: number | null;
  month: number | null;
  scope: BudgetScope;
  period_start: string;
  period_end: string;
  limit_amount: string;
  spent: string;
  remaining: string;
  utilization: string;
  over_budget: boolean;
}

export interface FundStatus {
  scope: BudgetScope;
  period_start: string;
  period_end: string;
  amount: string;
  is_override: boolean;
}

// ---------------------------------------------------------------- warehouse

export interface WarehouseStatus {
  ok: boolean;
  is_stale: boolean;
  last_loaded_at: string | null;
  oltp_lines: number;
  olap_lines: number;
  drift: number;
  integrity_problems: { entry_id: number | null; kind: string; detail: string }[];
  note: string | null;
  warehouse_path: string;
}
