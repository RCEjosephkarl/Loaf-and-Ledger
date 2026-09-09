import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { previousRangeBounds, rangeBounds, useFilters, type TimeRange } from "@/store/filters";
import type {
  Account,
  AccountBalances,
  AccountType,
  AnalyticsOverview,
  Breakdown,
  Budget,
  BudgetScope,
  BudgetStatus,
  DashboardSummary,
  EarningsResponse,
  EntryKind,
  EntrySource,
  FundStatus,
  JournalEntry,
  JournalLineInput,
  Meta,
  MonthlyByAccountResponse,
  MonthlyPoint,
  Payee,
  PayPeriod,
  RunningBalanceResponse,
  SalaryProfile,
  WarehouseStatus,
} from "@/lib/types";

/** Map the global time-range vocabulary to the backend's BudgetScope
 * vocabulary ("this_month" -> "month", "last_3m" -> "3m"; ytd/all match). */
export function toBudgetScope(range: TimeRange): BudgetScope {
  if (range === "this_month") return "month";
  if (range === "last_3m") return "3m";
  return range;
}

/** Global filter params shared by dashboard/analytics/ledger reads. */
export function useGlobalParams() {
  const { accountId, timeRange } = useFilters();
  const { start, end } = rangeBounds(timeRange);
  return {
    account_id: accountId ?? undefined,
    start: start || undefined,
    end: end || undefined,
  };
}

// ---- meta ----
export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: () => api.get<Meta>("/meta"), staleTime: Infinity });

// ---- accounts ----
export const useAccounts = (opts?: { includeArchived?: boolean; type?: AccountType }) =>
  useQuery({
    queryKey: ["accounts", "list", opts?.includeArchived ?? false, opts?.type ?? "all"],
    queryFn: () =>
      api.get<Account[]>("/accounts", {
        include_archived: opts?.includeArchived,
        type: opts?.type,
      }),
  });

export const useAccountBalances = () =>
  useQuery({
    queryKey: ["accounts", "balances"],
    queryFn: () => api.get<AccountBalances>("/accounts/balances"),
  });

export const useCreateAccount = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      code: string;
      name: string;
      type: AccountType;
      subtype?: string;
      opening_balance?: string;
    }) => api.post<Account>("/accounts", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
};

export const useUpdateAccount = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: number; name?: string; subtype?: string; is_active?: boolean }) =>
      api.patch<Account>(`/accounts/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
};

export const useArchiveAccount = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/accounts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
};

export const usePayees = () =>
  useQuery({ queryKey: ["payees"], queryFn: () => api.get<Payee[]>("/payees") });

export const useCreatePayee = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; default_account_id?: number }) =>
      api.post<Payee>("/payees", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payees"] }),
  });
};

// ---- ledger (journal) ----

/** Every write invalidates both stores' readers: the OLTP-backed lists and the
 * OLAP-backed analytics, which the server has already kept in step. */
const LEDGER_KEYS = [["entries"], ["accounts"], ["dashboard"], ["analytics"], ["budgets"], ["warehouse"]];

function useLedgerMutation<TInput, TResult>(fn: (input: TInput) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => LEDGER_KEYS.forEach((queryKey) => qc.invalidateQueries({ queryKey })),
  });
}

export const useEntries = (opts?: { source?: EntrySource; includeVoided?: boolean }) => {
  const p = useGlobalParams();
  const params = { ...p, source: opts?.source, include_voided: opts?.includeVoided };
  return useQuery({
    queryKey: ["entries", params],
    queryFn: () => api.get<JournalEntry[]>("/ledger/entries", params),
  });
};

/** Every entry ever recorded, ignoring the global range — the Ledger page's
 * running-balance column has to span the whole history to mean anything. */
export const useAllEntries = () => {
  const accountId = useFilters((s) => s.accountId);
  return useQuery({
    queryKey: ["entries", "all", accountId],
    queryFn: () =>
      api.get<JournalEntry[]>("/ledger/entries", {
        account_id: accountId ?? undefined,
        limit: 2000,
      }),
  });
};

export interface SimpleEntryInput {
  kind: EntryKind;
  amount: string;
  account_id: number;
  counter_account_id: number;
  occurred_at: string;
  memo?: string;
  payee_id?: number;
}

export const useCreateSimpleEntry = () =>
  useLedgerMutation((input: SimpleEntryInput) =>
    api.post<JournalEntry>("/ledger/entries/simple", input),
  );

export const useCreateEntry = () =>
  useLedgerMutation(
    (input: {
      occurred_at: string;
      lines: JournalLineInput[];
      memo?: string;
      payee_id?: number;
    }) => api.post<JournalEntry>("/ledger/entries", input),
  );

export const useUpdateEntry = () =>
  useLedgerMutation(
    ({
      id,
      ...patch
    }: {
      id: number;
      occurred_at?: string;
      lines?: JournalLineInput[];
      memo?: string;
    }) => api.patch<JournalEntry>(`/ledger/entries/${id}`, patch),
  );

export const useVoidEntry = () =>
  useLedgerMutation((id: number) => api.del(`/ledger/entries/${id}`));

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

export const useDeleteProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.del(`/salary/profiles/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["salary"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
};

/** Post a saved payslip to the ledger as one balanced multi-line entry. */
export const usePostPayslip = () =>
  useLedgerMutation((input: { id: number; deposit_account_id: number; occurred_at?: string }) =>
    api.post<{ entry: JournalEntry; created: boolean }>(`/salary/profiles/${input.id}/post`, {
      deposit_account_id: input.deposit_account_id,
      occurred_at: input.occurred_at,
    }),
  );

// ---- F3 analytics / F6 dashboard (all served from the warehouse) ----
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

/** The same endpoint over the immediately prior period of equal length —
 * powers every "Δ vs prior" comparison. */
export const usePreviousAnalyticsOverview = () => {
  const { accountId, timeRange } = useFilters();
  const prev = previousRangeBounds(timeRange);
  return useQuery({
    queryKey: ["analytics", "overview", "previous", accountId, timeRange],
    queryFn: () =>
      api.get<AnalyticsOverview>("/analytics/overview", {
        account_id: accountId ?? undefined,
        start: prev?.start,
        end: prev?.end,
      }),
    enabled: !!prev,
  });
};

/** How many trailing months the monthly charts should request for each preset,
 * so the chart's span tracks the selected scope instead of a fixed 6. */
export function monthsForRange(range: TimeRange): number {
  switch (range) {
    case "this_month":
      return 6; // trailing context around the selected month
    case "last_3m":
      return 3;
    case "ytd":
      return new Date().getMonth() + 1; // Jan..current month
    case "all":
      return 36; // the backend's own Query(..., le=36) ceiling
  }
}

export const useMonthly = () => {
  const timeRange = useFilters((s) => s.timeRange);
  const months = monthsForRange(timeRange);
  return useQuery({
    queryKey: ["analytics", "monthly", months],
    queryFn: () =>
      api.get<{ currency: string; series: MonthlyPoint[] }>("/analytics/monthly", { months }),
  });
};

export const useMonthlyByAccount = (months: number, flow: "inflow" | "outflow" = "outflow") =>
  useQuery({
    queryKey: ["analytics", "monthly-by-account", months, flow],
    queryFn: () =>
      api.get<MonthlyByAccountResponse>("/analytics/monthly-by-account", { months, flow }),
  });

/** Cumulative daily net cash flow. Defaults to the global range; pass an
 * explicit `{start,end}` so a page can drive it from its own period. */
export const useRunningBalance = (override?: { start?: string | null; end?: string | null }) => {
  const timeRange = useFilters((s) => s.timeRange);
  const { start, end } = override ?? rangeBounds(timeRange);
  const params = { start: start || undefined, end: end || undefined };
  return useQuery({
    queryKey: ["analytics", "running-balance", params],
    queryFn: () => api.get<RunningBalanceResponse>("/analytics/running-balance", params),
  });
};

/** The gross-to-net waterfall, read from fact_payslip_item. */
export const useEarnings = (profileId?: number) =>
  useQuery({
    queryKey: ["analytics", "earnings", profileId ?? "active"],
    queryFn: () => api.get<EarningsResponse>("/analytics/earnings", { profile_id: profileId }),
  });

// ---- F4 budgets ----
export const useBudgets = () =>
  useQuery({ queryKey: ["budgets", "list"], queryFn: () => api.get<Budget[]>("/budgets") });

export const useBudgetStatus = (scope: BudgetScope, anchor?: string) =>
  useQuery({
    queryKey: ["budgets", "status", scope, anchor],
    queryFn: () => api.get<BudgetStatus[]>("/budgets/status", { scope, anchor }),
  });

export const useBudgetFund = (scope: BudgetScope, anchor?: string) =>
  useQuery({
    queryKey: ["budgets", "fund", scope, anchor],
    queryFn: () => api.get<FundStatus>("/budgets/fund", { scope, anchor }),
  });

export const useSetBudgetFund = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { scope: BudgetScope; anchor?: string; amount: string }) =>
      api.post<FundStatus>("/budgets/fund", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets", "fund"] }),
  });
};

export const useResetBudgetFund = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { scope: BudgetScope; anchor?: string }) => api.del("/budgets/fund", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["budgets", "fund"] }),
  });
};

export const useUpsertBudget = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      account_id: number;
      year: number;
      month: number;
      limit_amount: string;
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

// ---- warehouse ----

/** Drift between the two stores. Polled gently: write-through keeps them in
 * step, so this is a safety net, not a status the user watches. */
export const useWarehouseStatus = () =>
  useQuery({
    queryKey: ["warehouse", "status"],
    queryFn: () => api.get<WarehouseStatus>("/warehouse/status"),
    staleTime: 30_000,
  });

export const useRebuildWarehouse = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ counts: Record<string, number> }>("/warehouse/rebuild"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["warehouse"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
};
