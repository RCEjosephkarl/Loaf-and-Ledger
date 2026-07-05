import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { rangeBounds, useFilters } from "@/store/filters";
import type {
  AnalyticsOverview,
  Breakdown,
  Budget,
  BudgetStatus,
  Category,
  DashboardSummary,
  Direction,
  MonthlyPoint,
  PayPeriod,
  Region,
  RegionInfo,
  SalaryProfile,
  Transaction,
} from "@/lib/types";

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

export const useTransactions = () => {
  const p = useGlobalParams();
  return useQuery({
    queryKey: ["transactions", p],
    queryFn: () => api.get<Transaction[]>("/ledger/transactions", p),
  });
};

export interface TxInput {
  direction: Direction;
  category_id: number;
  amount: string;
  currency?: string;
  region?: Region;
  occurred_on: string;
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

export const useMonthly = (months = 6) => {
  const { currency, region } = useGlobalParams();
  return useQuery({
    queryKey: ["analytics", "monthly", currency, region, months],
    queryFn: () =>
      api.get<{ currency: string; series: MonthlyPoint[] }>("/analytics/monthly", {
        currency,
        region,
        months,
      }),
  });
};

// ---- F4 budgets ----
export const useBudgets = () =>
  useQuery({ queryKey: ["budgets", "list"], queryFn: () => api.get<Budget[]>("/budgets") });

export const useBudgetStatus = (year: number, month: number) =>
  useQuery({
    queryKey: ["budgets", "status", year, month],
    queryFn: () => api.get<BudgetStatus[]>("/budgets/status", { year, month }),
  });

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
