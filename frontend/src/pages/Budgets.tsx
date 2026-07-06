import { useMemo, useState } from "react";
import {
  toBudgetScope,
  useBudgetFund,
  useBudgets,
  useBudgetStatus,
  useCategories,
  useDeleteBudget,
  useResetBudgetFund,
  useRunningBalance,
  useSetBudgetFund,
  useUpsertBudget,
} from "@/api/queries";
import { HoverTabs } from "@/components/HoverTabs";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { useChartPalette } from "@/lib/chartColors";
import { money, percent, shortDate } from "@/lib/format";
import { rangeBounds, TIME_RANGES, useFilters, type TimeRange } from "@/store/filters";

const now = new Date();

function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function Budgets() {
  const currency = useFilters((s) => s.currency);

  // Page-local period selector — deliberately independent of the global
  // top-bar time range, so switching it here doesn't affect other pages.
  const [scope, setScope] = useState<TimeRange>("this_month");
  const budgetScope = toBudgetScope(scope);
  const { start, end } = rangeBounds(scope);

  // The "Set a limit" form still targets one specific calendar month
  // (budgets are stored per-month regardless of the viewing scope above).
  const [formYear, setFormYear] = useState(now.getFullYear());
  const [formMonth, setFormMonth] = useState(now.getMonth() + 1);

  const { data: outCats } = useCategories("outbound");
  const { data: budgets } = useBudgets();
  const { data: status } = useBudgetStatus(budgetScope);
  const { data: fund } = useBudgetFund(budgetScope);
  const { data: runningBalance } = useRunningBalance({ start, end });
  const upsert = useUpsertBudget();
  const removeBudget = useDeleteBudget();
  const setFund = useSetBudgetFund();
  const resetFund = useResetBudgetFund();
  const palette = useChartPalette();

  const [categoryId, setCategoryId] = useState<number | "">("");
  const [limit, setLimit] = useState("");
  const [fundDraft, setFundDraft] = useState<string | null>(null);

  const formLimits = useMemo(
    () => budgets?.filter((b) => b.year === formYear && b.month === formMonth) ?? [],
    [budgets, formYear, formMonth],
  );

  const catName = useMemo(() => {
    const m = new Map<number, string>();
    outCats?.forEach((c) => m.set(c.id, c.name));
    return m;
  }, [outCats]);

  // KPI cards: whether current spending should be flagged.
  const kpis = useMemo(() => {
    const rows = status ?? [];
    const onTrack = rows.filter((s) => !s.over_budget && Number(s.utilization) < 0.8).length;
    const atRisk = rows.filter((s) => !s.over_budget && Number(s.utilization) >= 0.8).length;
    const over = rows.filter((s) => s.over_budget);
    const overAmount = over.reduce((sum, s) => sum + (Number(s.spent) - Number(s.limit_amount)), 0);

    let projected: { total: number; flagged: boolean } | null = null;
    if (budgetScope !== "all" && fund && rows.length) {
      const periodStart = parseLocalDate(fund.period_start);
      const periodEnd = parseLocalDate(fund.period_end);
      const totalDays = Math.round((periodEnd.getTime() - periodStart.getTime()) / 86_400_000) + 1;
      const elapsedDays = Math.min(
        Math.max(Math.round((now.getTime() - periodStart.getTime()) / 86_400_000) + 1, 1),
        totalDays,
      );
      const spentTotal = rows.reduce((sum, s) => sum + Number(s.spent), 0);
      const limitTotal = rows.reduce((sum, s) => sum + Number(s.limit_amount), 0);
      const total = (spentTotal / elapsedDays) * totalDays;
      projected = { total, flagged: total > limitTotal };
    }

    return { onTrack, atRisk, overCount: over.length, overAmount, projected };
  }, [status, fund, budgetScope]);

  const fundAmount = Number(fund?.amount ?? 0);
  const balancePoints = runningBalance?.points ?? [];
  const balanceChart = {
    labels: balancePoints.map((p) => shortDate(p.date)),
    series: [
      {
        label: "Balance",
        color: palette.green,
        fill: true,
        data: balancePoints.map((p) => Number(p.balance) + fundAmount),
      },
      { label: "Zero", color: palette.rule, dashed: true, data: balancePoints.map(() => 0) },
    ],
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (categoryId === "" || !limit) return;
    await upsert.mutateAsync({
      category_id: Number(categoryId),
      year: formYear,
      month: formMonth,
      limit_amount: limit,
      currency,
    });
    setLimit("");
  };

  const submitFund = async (e: React.FormEvent) => {
    e.preventDefault();
    if (fundDraft === null) return;
    await setFund.mutateAsync({ scope: budgetScope, amount: fundDraft, currency });
    setFundDraft(null);
  };

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">04 · Budgets</span>
        <h1>Lines drawn before you spend</h1>
        <p>
          Pick a period, see what you started it with, what you've allotted per category, and how
          the running balance is holding up.
        </p>
      </div>

      <div className="filterbar__segment" role="group" aria-label="Budget period" style={{ marginBottom: 20 }}>
        {TIME_RANGES.map((r) => (
          <button
            key={r.value}
            className={`seg ${scope === r.value ? "seg--on" : ""}`}
            onClick={() => setScope(r.value)}
          >
            {r.label}
          </button>
        ))}
      </div>

      <section className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="eyebrow">On track</span>
          <div className="stat__value fig">{kpis.onTrack}</div>
          <span className="stat__sub muted">categories under 80% used</span>
        </div>
        <div className="card stat">
          <span className="eyebrow">At risk</span>
          <div
            className="stat__value fig"
            style={kpis.atRisk > 0 ? { color: "var(--warn)" } : undefined}
          >
            {kpis.atRisk}
          </div>
          <span className="stat__sub muted">80%+ used, not over yet</span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Over budget</span>
          <div className={`stat__value fig ${kpis.overCount > 0 ? "fig--debit" : ""}`}>
            {kpis.overCount}
          </div>
          <span className="stat__sub muted">
            {kpis.overCount > 0 ? (
              <Money value={kpis.overAmount.toFixed(2)} currency={currency} sign="debit" />
            ) : (
              "—"
            )}{" "}
            over limit
          </span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Projected period-end</span>
          {kpis.projected ? (
            <>
              <div className={`stat__value fig ${kpis.projected.flagged ? "fig--debit" : "fig--credit"}`}>
                <Money value={kpis.projected.total.toFixed(2)} currency={currency} />
              </div>
              <span className="stat__sub muted">
                {kpis.projected.flagged ? "pacing over your limits" : "pacing within your limits"}
              </span>
            </>
          ) : (
            <>
              <div className="stat__value muted fig">—</div>
              <span className="stat__sub muted">
                {budgetScope === "all" ? "no fixed end to pace against" : "not enough data yet"}
              </span>
            </>
          )}
        </div>
      </section>

      <HoverTabs
        tabs={[
          {
            id: "by-category",
            label: "By category",
            content: (
              <div className="grid budget-grid">
                <section className="card">
                  <div className="card__head">
                    <h3>Set a limit</h3>
                  </div>
                  <div className="card__body">
                    <form className="stack" style={{ gap: 14 }} onSubmit={submit}>
                      <div className="row" style={{ gap: 10 }}>
                        <label className="inline-field" style={{ flex: 1 }}>
                          <span className="eyebrow">Month</span>
                          <select value={formMonth} onChange={(e) => setFormMonth(Number(e.target.value))}>
                            {months.map((m, i) => (
                              <option key={m} value={i + 1}>
                                {m}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="inline-field" style={{ flex: 1 }}>
                          <span className="eyebrow">Year</span>
                          <input
                            className="fig"
                            value={formYear}
                            onChange={(e) => setFormYear(Number(e.target.value) || formYear)}
                          />
                        </label>
                      </div>
                      <div className="field">
                        <label>Category</label>
                        <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value) || "")}>
                          <option value="">Choose…</option>
                          {outCats?.filter((c) => !c.statutory).map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label>Monthly limit ({currency})</label>
                        <input className="fig" inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} required />
                      </div>
                      <button className="btn btn--primary" type="submit" disabled={upsert.isPending}>
                        Save limit
                      </button>
                    </form>

                    {formLimits.length > 0 && (
                      <div className="stack" style={{ gap: 8, marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--rule)" }}>
                        <span className="eyebrow">
                          {months[formMonth - 1]} {formYear} limits
                        </span>
                        {formLimits.map((b) => (
                          <div key={b.id} className="row" style={{ justifyContent: "space-between", fontSize: 13 }}>
                            <span>{catName.get(b.category_id) ?? "—"}</span>
                            <span className="row" style={{ gap: 8 }}>
                              <Money value={b.limit_amount} currency={b.currency} />
                              <button className="btn" onClick={() => removeBudget.mutate(b.id)}>
                                ✕
                              </button>
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </section>

                <section className="card">
                  <div className="card__head">
                    <h3>{TIME_RANGES.find((r) => r.value === scope)?.label}</h3>
                    <span className="eyebrow">allotted vs. spent</span>
                  </div>
                  <div className="card__body">
                    {!status?.length ? (
                      <div className="empty">No budgets set for this period.</div>
                    ) : (
                      <div className="stack" style={{ gap: 16 }}>
                        {status.map((s) => {
                          const util = Math.min(Number(s.utilization), 1);
                          return (
                            <div key={s.category_id} className="budget-row">
                              <div className="budget-row__head">
                                <span>{s.category_name}</span>
                                <span className="fig">
                                  <Money value={s.spent} currency={s.currency} /> /{" "}
                                  <span className="muted">
                                    <Money value={s.limit_amount} currency={s.currency} />
                                  </span>
                                </span>
                              </div>
                              <div className="bar__track">
                                <div
                                  className={`bar__fill ${s.over_budget ? "bar__fill--over" : ""}`}
                                  style={{ width: `${util * 100}%` }}
                                />
                              </div>
                              <div className="budget-row__foot">
                                <span className={s.over_budget ? "fig fig--debit" : "muted fig"}>
                                  {percent(s.utilization, 0)} used
                                </span>
                                <span className={Number(s.remaining) < 0 ? "fig fig--debit" : "fig fig--credit"}>
                                  <Money value={s.remaining} currency={s.currency} /> left
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </section>
              </div>
            ),
          },
          {
            id: "trend",
            label: "Trend",
            content: (
              <div className="grid" style={{ gap: 20 }}>
                <section className="card">
                  <div className="card__head">
                    <h3>Initial fund</h3>
                    <span className="eyebrow">{fund?.is_override ? "custom" : "carried over"}</span>
                  </div>
                  <div className="card__body">
                    <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
                      Carried over from the prior period's ending balance. Override it if your real
                      starting point differs.
                    </p>
                    {fundDraft === null ? (
                      <div className="row" style={{ gap: 14, alignItems: "center", flexWrap: "wrap" }}>
                        <div className="stat__value">
                          <Money value={fund?.amount ?? "0"} currency={currency} />
                        </div>
                        <button className="btn" onClick={() => setFundDraft(fund?.amount ?? "0")}>
                          Edit
                        </button>
                        {fund?.is_override && (
                          <button
                            className="btn"
                            onClick={() => resetFund.mutate({ scope: budgetScope })}
                            disabled={resetFund.isPending}
                          >
                            Reset to computed default
                          </button>
                        )}
                      </div>
                    ) : (
                      <form className="row" style={{ gap: 10 }} onSubmit={submitFund}>
                        <input
                          className="fig"
                          inputMode="decimal"
                          value={fundDraft}
                          onChange={(e) => setFundDraft(e.target.value)}
                          autoFocus
                        />
                        <button className="btn btn--primary" type="submit" disabled={setFund.isPending}>
                          Save
                        </button>
                        <button className="btn" type="button" onClick={() => setFundDraft(null)}>
                          Cancel
                        </button>
                      </form>
                    )}
                  </div>
                </section>

                <section className="card">
                  <div className="card__head">
                    <h3>Running balance</h3>
                    <span className="eyebrow">this period, starting from your initial fund</span>
                  </div>
                  <div className="card__body">
                    <LineChart
                      labels={balanceChart.labels}
                      series={balanceChart.series}
                      valueFormatter={(v) => money(v, currency)}
                    />
                  </div>
                </section>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
