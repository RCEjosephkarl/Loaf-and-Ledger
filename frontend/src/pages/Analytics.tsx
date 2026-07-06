import { useMemo } from "react";
import {
  monthsForRange,
  useAnalyticsOverview,
  useMonthly,
  useMonthlyByCategory,
  usePreviousAnalyticsOverview,
  useRunningBalance,
  useTransactions,
} from "@/api/queries";
import { BarChart } from "@/components/BarChart";
import { HoverTabs } from "@/components/HoverTabs";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { StackedBarChart } from "@/components/StackedBarChart";
import { useChartPalette } from "@/lib/chartColors";
import { formatTime, money, percent, shortDate, signedPercent } from "@/lib/format";
import { rangeBounds, useFilters } from "@/store/filters";

/** Average expense per hour/day/week/month over the active range (burn rate). */
function useBurnRate(totalExpense: string | undefined) {
  const timeRange = useFilters((s) => s.timeRange);
  return useMemo(() => {
    const { start, end } = rangeBounds(timeRange);
    if (!start || !end || !totalExpense) return null;
    const days =
      Math.round((new Date(end).getTime() - new Date(start).getTime()) / 86_400_000) + 1;
    const perDay = Number(totalExpense) / Math.max(days, 1);
    return { perHour: perDay / 24, perDay, perWeek: perDay * 7, perMonth: perDay * 30.44 };
  }, [totalExpense, timeRange]);
}

export function Analytics() {
  const { data: overview, isLoading } = useAnalyticsOverview();
  const timeRange = useFilters((s) => s.timeRange);
  const { data: monthly } = useMonthly();
  const { data: monthlyByCategory } = useMonthlyByCategory(monthsForRange(timeRange));
  const { data: prevOverview } = usePreviousAnalyticsOverview();
  const { data: runningBalance } = useRunningBalance();
  const { data: expenseTxns } = useTransactions("outbound");
  const palette = useChartPalette();

  const income = overview?.categories.filter((c) => c.direction === "inbound") ?? [];
  const expense = overview?.categories.filter((c) => c.direction === "outbound") ?? [];
  const ccy = overview?.currency ?? "USD";
  const burnRate = useBurnRate(overview?.total_expense);

  const prevExpenseByName = useMemo(() => {
    const m = new Map<string, number>();
    prevOverview?.categories
      .filter((c) => c.direction === "outbound")
      .forEach((c) => m.set(c.category_name, Number(c.total)));
    return m;
  }, [prevOverview]);

  const cashFlow = useMemo(() => {
    const points = runningBalance?.points ?? [];
    return {
      labels: points.map((p) => shortDate(p.date)),
      series: [
        {
          label: "Running balance",
          color: palette.green,
          fill: true,
          data: points.map((p) => Number(p.balance)),
        },
      ],
    };
  }, [runningBalance, palette]);

  const expenseDeltas = useMemo(() => {
    const sorted = [...(expenseTxns ?? [])].sort((a, b) => {
      const da = `${a.occurred_on}T${a.occurred_time ?? "00:00"}`;
      const db = `${b.occurred_on}T${b.occurred_time ?? "00:00"}`;
      return da === db ? a.id - b.id : da.localeCompare(db);
    });
    const recent = sorted.slice(-20);
    return {
      labels: recent.map((t) => `${t.occurred_on.slice(5)} ${formatTime(t.occurred_time)}`),
      amounts: recent.map((t) => Number(t.amount)),
      deltas: recent.map((t, i) =>
        i === 0 ? null : Number(t.amount) - Number(recent[i - 1].amount),
      ),
    };
  }, [expenseTxns]);

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">05 · Analytics</span>
        <h1>Cross-referenced</h1>
        <p>
          What your salary math (F1) and your ledger (F2) say together: how much of gross survives to
          net, where the rest goes, and the shape of the last few months.
        </p>
      </div>

      {isLoading && <div className="empty">Crunching…</div>}

      {overview && (
        <div className="grid" style={{ gap: 20 }}>
          <section className="stat-grid">
            <div className="card stat">
              <span className="eyebrow">Total income</span>
              <div className="stat__value">
                <Money value={overview.total_income} currency={ccy} sign="credit" />
              </div>
            </div>
            <div className="card stat">
              <span className="eyebrow">Total expense</span>
              <div className="stat__value">
                <Money value={overview.total_expense} currency={ccy} sign="debit" />
              </div>
            </div>
            <div className="card stat">
              <span className="eyebrow">Net cash flow</span>
              <div className="stat__value">
                <Money
                  value={overview.net_cashflow}
                  currency={ccy}
                  sign={Number(overview.net_cashflow) >= 0 ? "credit" : "debit"}
                />
              </div>
            </div>
            <div className="card stat">
              <span className="eyebrow">Savings rate</span>
              <div className="stat__value fig">{percent(overview.savings_rate, 0)}</div>
            </div>
            <div className="card stat">
              <span className="eyebrow">Salary deduction rate</span>
              <div className="stat__value fig">
                {overview.salary_deduction_rate ? percent(overview.salary_deduction_rate, 1) : "—"}
              </div>
              <span className="stat__sub muted">gross lost to tax + contributions</span>
            </div>
          </section>

          <HoverTabs
            tabs={[
              {
                id: "overview",
                label: "Overview",
                content: (
                  <div className="grid analytics-cols">
                    <section className="card">
                      <div className="card__head">
                        <h3>Burn rate</h3>
                        <span className="eyebrow">avg. expense</span>
                      </div>
                      <div className="card__body">
                        {!burnRate ? (
                          <div className="empty">Pick a specific range (not "All") to see a burn rate.</div>
                        ) : (
                          <table className="ledger">
                            <tbody>
                              <tr>
                                <td>Per hour</td>
                                <td className="num"><Money value={burnRate.perHour.toFixed(2)} currency={ccy} sign="debit" /></td>
                              </tr>
                              <tr>
                                <td>Per day</td>
                                <td className="num"><Money value={burnRate.perDay.toFixed(2)} currency={ccy} sign="debit" /></td>
                              </tr>
                              <tr>
                                <td>Per week</td>
                                <td className="num"><Money value={burnRate.perWeek.toFixed(2)} currency={ccy} sign="debit" /></td>
                              </tr>
                              <tr>
                                <td>Per month</td>
                                <td className="num"><Money value={burnRate.perMonth.toFixed(2)} currency={ccy} sign="debit" /></td>
                              </tr>
                            </tbody>
                          </table>
                        )}
                      </div>
                    </section>

                    <section className="card">
                      <div className="card__head">
                        <h3>Monthly income vs. expense</h3>
                        <span className="pill">{ccy}</span>
                      </div>
                      <div className="card__body">
                        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
                          Bars show what came in and went out each month; the line traces the net —
                          above zero and the loaf is rising.
                        </p>
                        <BarChart series={monthly?.series ?? []} currency={ccy} />
                      </div>
                    </section>
                  </div>
                ),
              },
              {
                id: "trends",
                label: "Trends",
                content: (
                  <div className="grid analytics-cols">
                    <section className="card">
                      <div className="card__head">
                        <h3>Cash flow trend</h3>
                        <span className="eyebrow">cumulative</span>
                      </div>
                      <div className="card__body">
                        <LineChart
                          labels={cashFlow.labels}
                          series={cashFlow.series}
                          valueFormatter={(v) => money(v, ccy)}
                        />
                      </div>
                    </section>

                    <section className="card">
                      <div className="card__head">
                        <h3>Change in expense between transactions</h3>
                        <span className="eyebrow">last 20</span>
                      </div>
                      <div className="card__body">
                        <LineChart
                          labels={expenseDeltas.labels}
                          series={[
                            { label: "Amount", color: palette.crust, data: expenseDeltas.amounts },
                            { label: "Δ vs previous", color: palette.debit, data: expenseDeltas.deltas },
                          ]}
                          valueFormatter={(v) => v.toFixed(2)}
                        />
                      </div>
                    </section>
                  </div>
                ),
              },
              {
                id: "categories",
                label: "Categories",
                content: (
                  <div className="grid" style={{ gap: 20 }}>
                    <div className="grid analytics-cols">
                      <section className="card">
                        <div className="card__head">
                          <h3>Income by category</h3>
                        </div>
                        <div className="card__body">
                          {!income.length ? (
                            <div className="empty">No income in range.</div>
                          ) : (
                            <table className="ledger">
                              <tbody>
                                {income.map((c) => (
                                  <tr key={c.category_name}>
                                    <td>{c.category_name}</td>
                                    <td className="num">
                                      <Money value={c.total} currency={ccy} sign="credit" />
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </section>

                      <section className="card">
                        <div className="card__head">
                          <h3>Expense by category</h3>
                          <span className="eyebrow">Δ = inflation/deflation vs prior period</span>
                        </div>
                        <div className="card__body">
                          {!expense.length ? (
                            <div className="empty">No expenses in range.</div>
                          ) : (
                            <table className="ledger">
                              <thead>
                                <tr>
                                  <th>Category</th>
                                  <th className="num">Spent</th>
                                  {timeRange !== "all" && <th className="num">Δ vs prior</th>}
                                </tr>
                              </thead>
                              <tbody>
                                {expense
                                  .sort((a, b) => Number(b.total) - Number(a.total))
                                  .map((c) => {
                                    const prev = prevExpenseByName.get(c.category_name);
                                    const change = prev && prev > 0 ? (Number(c.total) - prev) / prev : null;
                                    return (
                                      <tr key={c.category_name}>
                                        <td>{c.category_name}</td>
                                        <td className="num">
                                          <Money value={c.total} currency={ccy} sign="debit" />
                                        </td>
                                        {timeRange !== "all" && (
                                          <td className="num">
                                            {change === null ? (
                                              <span className="muted">—</span>
                                            ) : (
                                              <span className={change > 0 ? "fig fig--debit" : "fig fig--credit"}>
                                                {signedPercent(change)}
                                              </span>
                                            )}
                                          </td>
                                        )}
                                      </tr>
                                    );
                                  })}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </section>
                    </div>

                    <section className="card">
                      <div className="card__head">
                        <h3>Expense mix over time</h3>
                        <span className="eyebrow">stacked by category</span>
                      </div>
                      <div className="card__body">
                        <StackedBarChart
                          months={monthlyByCategory?.months ?? []}
                          series={monthlyByCategory?.series ?? []}
                          currency={monthlyByCategory?.currency ?? ccy}
                        />
                      </div>
                    </section>
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
