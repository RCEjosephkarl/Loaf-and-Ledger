import { useDashboard } from "@/api/queries";
import { Money } from "@/components/Money";
import { percent } from "@/lib/format";
import type { Insight } from "@/lib/types";

function InsightRow({ i }: { i: Insight }) {
  return (
    <li className={`insight insight--${i.severity}`}>
      <span className="insight__dot" aria-hidden />
      <div>
        <div className="insight__title">{i.title}</div>
        <div className="insight__detail muted">{i.detail}</div>
      </div>
    </li>
  );
}

export function Dashboard() {
  const { data, isLoading, isError, error } = useDashboard();

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">The books</span>
        <h1>Where the dough goes</h1>
        <p>
          A running balance of what comes in and what goes out — with plain-spoken notes on how
          you're tracking. Adjust the range, region, and currency up top; every figure follows.
        </p>
      </div>

      {isLoading && <div className="empty">Tallying the ledger…</div>}
      {isError && <div className="empty empty--error">Couldn't load the summary: {String(error)}</div>}

      {data && (
        <div className="grid dash-grid">
          {/* Hero: balance sheet */}
          <section className="card balance">
            <div className="card__head">
              <h3>Balance</h3>
              <span className="pill">{data.currency}</span>
            </div>
            <div className="card__body">
              <table className="ledger balance__table">
                <tbody>
                  <tr>
                    <td>Credits · money in</td>
                    <td className="num">
                      <Money value={data.total_income} currency={data.currency} sign="credit" />
                    </td>
                  </tr>
                  <tr>
                    <td>Debits · money out</td>
                    <td className="num">
                      <Money value={`-${data.total_expense}`} currency={data.currency} sign="debit" />
                    </td>
                  </tr>
                  <tr className="total">
                    <td>Net cashflow</td>
                    <td className="num">
                      <Money
                        value={data.net_cashflow}
                        currency={data.currency}
                        sign={Number(data.net_cashflow) >= 0 ? "credit" : "debit"}
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Secondary stats */}
          <section className="stat-col">
            <div className="card stat">
              <span className="eyebrow">Savings rate</span>
              <div className="stat__value fig">{percent(data.savings_rate, 0)}</div>
              <span className="stat__sub muted">of reference income kept this period</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Salary · net / period</span>
              <div className="stat__value">
                {data.salary_net_period ? (
                  <Money value={data.salary_net_period} currency={data.currency} />
                ) : (
                  <span className="muted fig">—</span>
                )}
              </div>
              <span className="stat__sub muted">from your active salary profile</span>
            </div>
          </section>

          {/* Insights */}
          <section className="card insights">
            <div className="card__head">
              <h3>Notes from the ledger</h3>
              <span className="eyebrow">rule-based</span>
            </div>
            <div className="card__body">
              <ul className="insight-list">
                {data.insights.map((i) => (
                  <InsightRow key={i.key} i={i} />
                ))}
              </ul>
            </div>
          </section>

          {/* Top expenses */}
          <section className="card">
            <div className="card__head">
              <h3>Heaviest expenses</h3>
            </div>
            <div className="card__body">
              {data.top_expense_categories.length === 0 ? (
                <div className="empty">No expenses in range.</div>
              ) : (
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th className="num">Spent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_expense_categories.map((c) => (
                      <tr key={c.category_id ?? c.category_name}>
                        <td>{c.category_name}</td>
                        <td className="num">
                          <Money value={c.total} currency={data.currency} sign="debit" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
