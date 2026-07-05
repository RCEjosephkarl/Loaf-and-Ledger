import { useAnalyticsOverview, useMonthly } from "@/api/queries";
import { BarChart } from "@/components/BarChart";
import { Money } from "@/components/Money";
import { percent } from "@/lib/format";

export function Analytics() {
  const { data: overview, isLoading } = useAnalyticsOverview();
  const { data: monthly } = useMonthly(6);

  const income = overview?.categories.filter((c) => c.direction === "inbound") ?? [];
  const expense = overview?.categories.filter((c) => c.direction === "outbound") ?? [];
  const ccy = overview?.currency ?? "USD";

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

          <section className="card">
            <div className="card__head">
              <h3>Last 6 months</h3>
              <span className="pill">{ccy}</span>
            </div>
            <div className="card__body">
              <BarChart series={monthly?.series ?? []} currency={ccy} />
            </div>
          </section>

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
              </div>
              <div className="card__body">
                {!expense.length ? (
                  <div className="empty">No expenses in range.</div>
                ) : (
                  <table className="ledger">
                    <tbody>
                      {expense
                        .sort((a, b) => Number(b.total) - Number(a.total))
                        .map((c) => (
                          <tr key={c.category_name}>
                            <td>{c.category_name}</td>
                            <td className="num">
                              <Money value={c.total} currency={ccy} sign="debit" />
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
