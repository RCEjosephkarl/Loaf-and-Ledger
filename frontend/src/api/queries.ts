import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { previousRangeBounds, type DateBounds, type TimeRange } from "@/store/filters";
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
  FundStatus,
  JournalEntry,
  JournalEntryPage,
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

/** Map the frontend period vocabulary to the backend's BudgetScope
 * vocabulary ("this_month" -> "month", "last_3m" -> "3m"; ytd/all match). */
export function toBudgetScope(range: TimeRange): BudgetScope {
  if (range === "this_month") return "month";
  if (range === "last_3m") return "3m";
  return range;
}

/** Include explicit date bounds in both requests and cache keys. */
function dateParams(bounds: DateBounds = {}) {
  return { start: bounds.start || undefined, end: bounds.end || undefined };
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

export const useAccountBalances = (bounds: DateBounds = {}, includeArchived = false) =>
  useQuery({
    queryKey: ["accounts", "balances", dateParams(bounds), includeArchived],
    queryFn: () => api.get<AccountBalances>("/accounts/balances", {
      ...dateParams(bounds), include_archived: includeArchived,
    }),
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

export const useEntryPage = (page: number) => useQuery({
  queryKey: ["entries", "page", page],
  queryFn: () => api.get<JournalEntryPage>("/ledger/entries/page", { page, page_size: 10 }),
});

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

export const useActivateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<SalaryProfile>(`/salary/profiles/${id}/activate`),
    onSuccess: (profile) => {
      qc.setQueryData(["salary", "active"], profile);
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
export const useDashboard = (bounds: DateBounds) => {
  const p = dateParams(bounds);
  return useQuery({
    queryKey: ["dashboard", p],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary", p),
  });
};

export const useAnalyticsOverview = (bounds: DateBounds) => {
  const p = dateParams(bounds);
  return useQuery({
    queryKey: ["analytics", "overview", p],
    queryFn: () => api.get<AnalyticsOverview>("/analytics/overview", p),
  });
};

/** The same endpoint over the immediately prior period of equal length —
 * powers every "Δ vs prior" comparison. */
export const usePreviousAnalyticsOverview = (timeRange: TimeRange) => {
  const prev = previousRangeBounds(timeRange);
  return useQuery({
    queryKey: ["analytics", "overview", "previous", prev],
    queryFn: () =>
      api.get<AnalyticsOverview>("/analytics/overview", {
        start: prev?.start,
        end: prev?.end,
      }),
    enabled: !!prev,
  });
};

export const useMonthly = (bounds: DateBounds) => {
  const params = dateParams(bounds);
  return useQuery({
    queryKey: ["analytics", "monthly", params],
    queryFn: () => api.get<{ currency: string; series: MonthlyPoint[] }>("/analytics/monthly", params),
  });
};

export const useMonthlyByAccount = (bounds: DateBounds, flow: "inflow" | "outflow" = "outflow") => {
  const params = { ...dateParams(bounds), flow };
  return useQuery({
    queryKey: ["analytics", "monthly-by-account", params],
    queryFn: () => api.get<MonthlyByAccountResponse>("/analytics/monthly-by-account", params),
  });
};

export const useRunningBalance = (bounds: DateBounds) => {
  const params = dateParams(bounds);
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
