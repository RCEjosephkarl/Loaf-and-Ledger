import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { localISODate } from "@/lib/format";
import { previousRangeBounds, rangeBounds, useFilters, type TimeRange } from "@/store/filters";
import type {
  AnalyticsOverview,
  Breakdown,
  Budget,
  BudgetScope,
  BudgetStatus,
  Category,
  DashboardSummary,
  Direction,
  FundStatus,
  FxRatesResponse,
  MonthlyByCategoryResponse,
  MonthlyPoint,
  PayPeriod,
  Region,
  RegionInfo,
  RunningBalanceResponse,
  SalaryProfile,
  Transaction,
  TransactionBalancesResponse,
  TransactionUpdate,
} from "@/lib/types";

/** Map the global/page time-range vocabulary to the backend's BudgetScope
 * vocabulary ("this_month" -> "month", "last_3m" -> "3m"; ytd/all match). */
export function toBudgetScope(range: TimeRange): BudgetScope {
  if (range === "this_month") return "month";
  if (range === "last_3m") return "3m";
  return range;
}

/** Global filter params (F6) shared by dashboard/analytics/ledger reads. */
export function useGlobalParams() {
  const { region, currency, timeRange } = useFilters();
  const { start, end } = rangeBounds(timeRange);
  return {
    currency,
    region: region || undefined,
    start: start || undefined,
    end: end || undefined,
  };
}

// ---- meta ----
export const useRegions = () =>
  useQuery({ queryKey: ["regions"], queryFn: () => api.get<RegionInfo[]>("/regions") });

// ---- F1 salary ----
export const useActiveSalary = () =>
  useQuery({
    queryKey: ["salary", "active"],
    queryFn: () => api.get<SalaryProfile | null>("/salary/profiles/active"),
  });

export const useSalaryProfiles = () =>
  useQuery({
    queryKey: ["salary", "profiles"],
    queryFn: () => api.get<SalaryProfile[]>("/salary/profiles"),
  });

export interface CalcInput {
  region: Region;
  gross_amount: string;
  pay_period: PayPeriod;
}

export const useCalculate = () =>
  useMutation({
    mutationFn: (input: CalcInput) => api.post<Breakdown>("/salary/calculate", input),
  });

export const useSaveProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CalcInput & { label: string }) =>
      api.post<SalaryProfile>("/salary/profiles", { ...input, make_active: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["salary"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
};

export const useActivateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<SalaryProfile>(`/salary/profiles/${id}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["salary"] }),
  });
};

export const useDeleteProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/salary/profiles/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["salary"] }),
  });
};

// ---- F2 ledger ----
export const useCategories = (direction?: Direction) =>
  useQuery({
    queryKey: ["categories", direction ?? "all"],
    queryFn: () => api.get<Category[]>("/ledger/categories", { direction }),
  });

export const useTransactions = (direction?: Direction) => {
  const p = useGlobalParams();
  const params = { ...p, direction };
  return useQuery({
    queryKey: ["transactions", params],
    queryFn: () => api.get<Transaction[]>("/ledger/transactions", params),
  });
};

/** Full-history cumulative balance per transaction, keyed by id — feeds the
 * Ledger table's running-balance column. Always spans the user's whole
 * history regardless of the global time-range filter (see useGlobalBalance
 * for the equivalent single-figure card). */
export const useTransactionBalances = () => {
  const { region, currency } = useFilters();
  return useQuery({
    queryKey: ["transactions", "balances", region, currency],
    queryFn: () =>
      api.get<TransactionBalancesResponse>("/ledger/transactions/balances", {
        region: region || undefined,
        currency,
      }),
  });
};

export interface TxInput {
  direction: Direction;
  category_id: number;
  amount: string;
  currency?: string;
  region?: Region;
  occurred_on: string;
  occurred_time?: string;
  description?: string;
}

export const useCreateTransaction = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TxInput) => api.post<Transaction>("/ledger/transactions", input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
    },
  });
};

export const useUpdateTransaction = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: number } & TransactionUpdate) =>
      api.patch<Transaction>(`/ledger/transactions/${id}`, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      qc.invalidateQueries({ queryKey: ["budgets"] });
    },
  });
};

export const useDeleteTransaction = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/ledger/transactions/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
};

// ---- F3 analytics / F6 dashboard ----
export const useDashboard = () => {
  const p = useGlobalParams();
  return useQuery({
    queryKey: ["dashboard", p],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary", p),
  });
};

export const useAnalyticsOverview = () => {
  const p = useGlobalParams();
  return useQuery({
    queryKey: ["analytics", "overview", p],
    queryFn: () => api.get<AnalyticsOverview>("/analytics/overview", p),
  });
};

/** How many trailing months the monthly bar/combo chart should request for
 * each global time-range preset — keeps the chart's span aligned with the
 * selected scope instead of always showing a hardcoded 6 months. */
export function monthsForRange(range: TimeRange): number {
  switch (range) {
    case "this_month":
      return 6; // trailing context around the selected month
    case "last_3m":
      return 3;
    case "ytd":
      return new Date().getMonth() + 1; // Jan..current month
    case "all":
      return 36; // backend's own Query(..., le=36) ceiling
  }
}

export const useMonthly = () => {
  const { currency, region, timeRange } = useFilters();
  const months = monthsForRange(timeRange);
  return useQuery({
    queryKey: ["analytics", "monthly", currency, region, months],
    queryFn: () =>
      api.get<{ currency: string; series: MonthlyPoint[] }>("/analytics/monthly", {
        currency,
        region: region || undefined,
        months,
      }),
  });
};

export const useMonthlyByCategory = (months: number) => {
  const { currency, region } = useFilters();
  return useQuery({
    queryKey: ["analytics", "monthly-by-category", currency, region, months],
    queryFn: () =>
      api.get<MonthlyByCategoryResponse>("/analytics/monthly-by-category", {
        currency,
        region: region || undefined,
        months,
      }),
  });
};

/** Cumulative daily net cash flow. Defaults to the global time-range filter;
 * pass an explicit `{start,end}` override so a page (e.g. Budgets) can drive
 * this from its own local period instead of the global one. */
export const useRunningBalance = (override?: { start?: string | null; end?: string | null }) => {
  const { region, currency, timeRange } = useFilters();
  const { start, end } = override ?? rangeBounds(timeRange);
  const params = { currency, region: region || undefined, start: start || undefined, end: end || undefined };
  return useQuery({
    queryKey: ["analytics", "running-balance", params],
    queryFn: () => api.get<RunningBalanceResponse>("/analytics/running-balance", params),
  });
};

/** Same `/analytics/overview` endpoint, re-queried over the immediately prior
 * period of equal length — powers the "Δ vs prior period" comparison. */
export const usePreviousAnalyticsOverview = () => {
  const { region, currency, timeRange } = useFilters();
  const prev = previousRangeBounds(timeRange);
  return useQuery({
    queryKey: ["analytics", "overview", "previous", region, currency, timeRange],
    queryFn: () =>
      api.get<AnalyticsOverview>("/analytics/overview", {
        currency,
        region: region || undefined,
        start: prev?.start,
        end: prev?.end,
      }),
    enabled: !!prev,
  });
};

// ---- FX live rates (Dashboard) ----

/** `rangeBounds("all")` returns nulls, which on `/fx/rates` means "give the
 * legacy 7-day default" — not what "All" should mean for this chart. Map it
 * to an explicit 365-day lookback instead; every other preset passes through. */
function fxRangeBounds(range: TimeRange): { start: string | null; end: string | null } {
  if (range === "all") {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 365);
    return { start: localISODate(start), end: localISODate(end) };
  }
  return rangeBounds(range);
}

export const useFxRates = () => {
  const { currency, timeRange } = useFilters();
  const { start, end } = fxRangeBounds(timeRange);
  return useQuery({
    queryKey: ["fx", "rates", currency, start, end],
    queryFn: () => api.get<FxRatesResponse>("/fx/rates", { base: currency, start, end }),
    staleTime: 60 * 60 * 1000, // daily close rates — no need to refetch often
  });
};

// ---- F4 budgets ----
export const useBudgets = () =>
  useQuery({ queryKey: ["budgets", "list"], queryFn: () => api.get<Budget[]>("/budgets") });

export const useBudgetStatus = (scope: BudgetScope, anchor?: string) =>
  useQuery({
    queryKey: ["budgets", "status", scope, anchor],
    queryFn: () => api.get<BudgetStatus[]>("/budgets/status", { scope, anchor }),
  });

export const useBudgetFund = (scope: BudgetScope, anchor?: string) => {
  const currency = useFilters((s) => s.currency);
  return useQuery({
    queryKey: ["budgets", "fund", scope, anchor, currency],
    queryFn: () => api.get<FundStatus>("/budgets/fund", { scope, anchor, currency }),
  });
};

export const useSetBudgetFund = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { scope: BudgetScope; anchor?: string; amount: string; currency?: string }) =>
      api.post<FundStatus>("/budgets/fund", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets", "fund"] }),
  });
};

export const useResetBudgetFund = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { scope: BudgetScope; anchor?: string }) =>
      api.del("/budgets/fund", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets", "fund"] }),
  });
};

export const useUpsertBudget = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      category_id: number;
      year: number;
      month: number;
      limit_amount: string;
      currency?: string;
    }) => api.post<Budget>("/budgets", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets"] }),
  });
};

export const useDeleteBudget = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/budgets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets"] }),
  });
};
