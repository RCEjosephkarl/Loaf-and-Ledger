export type Region = "PH" | "US" | "AU" | "EU";
export type Direction = "inbound" | "outbound";
export type PayPeriod = "monthly" | "annual";
export type BudgetScope = "month" | "3m" | "ytd" | "all";

export interface RegionInfo {
  region: Region;
  name: string;
  currency: string;
  modelled_as: string;
  supported: boolean;
}

export interface LineItem {
  key: string;
  label: string;
  amount: string;
  kind: "gross" | "tax" | "social" | "net" | "info";
}

export interface Breakdown {
  region: string;
  currency: string;
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
  region: Region;
  currency: string;
  gross_amount: string;
  pay_period: PayPeriod;
  tax_year: number;
  net_amount: string;
  total_deductions: string;
  breakdown: Breakdown;
  is_active: boolean;
}

export interface Category {
  id: number;
  name: string;
  direction: Direction;
  statutory: boolean;
  region: Region | null;
  is_system: boolean;
}

export interface Transaction {
  id: number;
  direction: Direction;
  category_id: number;
  amount: string;
  currency: string;
  region: Region | null;
  occurred_on: string;
  occurred_time: string | null;
  description: string | null;
}

export interface TransactionUpdate {
  category_id?: number;
  amount?: string;
  currency?: string;
  occurred_on?: string;
  occurred_time?: string;
  description?: string;
}

export interface CategoryTotal {
  category_id: number | null;
  category_name: string;
  direction: Direction;
  total: string;
}

export interface Insight {
  key: string;
  severity: "info" | "warning" | "good";
  title: string;
  detail: string;
}

export interface DashboardSummary {
  currency: string;
  region: Region | null;
  total_income: string;
  total_expense: string;
  net_cashflow: string;
  salary_net_period: string | null;
  savings_rate: string;
  top_expense_categories: CategoryTotal[];
  insights: Insight[];
}

export interface AnalyticsOverview {
  currency: string;
  total_income: string;
  total_expense: string;
  net_cashflow: string;
  salary_net_period: string | null;
  salary_deduction_rate: string | null;
  savings_rate: string;
  categories: CategoryTotal[];
}

export interface MonthlyPoint {
  month: string;
  income: string;
  expense: string;
  net: string;
}

export interface Budget {
  id: number;
  category_id: number;
  year: number;
  month: number;
  limit_amount: string;
  currency: string;
}

export interface BudgetStatus {
  category_id: number;
  category_name: string;
  year: number | null;
  month: number | null;
  scope: BudgetScope;
  period_start: string;
  period_end: string;
  limit_amount: string;
  spent: string;
  remaining: string;
  utilization: string;
  currency: string;
  over_budget: boolean;
}

export interface FundStatus {
  scope: BudgetScope;
  period_start: string;
  period_end: string;
  amount: string;
  currency: string;
  is_override: boolean;
}

export interface MonthlyCategorySeries {
  category_id: number | null;
  category_name: string;
  values: string[];
}

export interface MonthlyByCategoryResponse {
  currency: string;
  months: string[];
  series: MonthlyCategorySeries[];
}

export interface FxRatePoint {
  date: string;
  rates: Record<string, string>;
}

export interface FxRatesResponse {
  base: string;
  quotes: string[];
  live: boolean;
  as_of: string | null;
  series: FxRatePoint[];
}

export interface RunningBalancePoint {
  date: string;
  income: string;
  expense: string;
  net: string;
  balance: string;
}

export interface RunningBalanceResponse {
  currency: string;
  points: RunningBalancePoint[];
}

export interface TransactionBalancesResponse {
  currency: string;
  balances: Record<number, string>;
}
