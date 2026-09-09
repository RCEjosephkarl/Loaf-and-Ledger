import { useMemo } from "react";
import { useDashboard, useMonthly, useRunningBalance } from "@/api/queries";
import { BarChart } from "@/components/BarChart";
import { HighlightCard } from "@/components/HighlightCard";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { useChartPalette } from "@/lib/chartColors";
import { money, moneyShort, percent, shortDate } from "@/lib/format";
import { timeRangeLabel, useFilters } from "@/store/filters";
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

function BalanceTrendCard() {
  const timeRange = useFilters((s) => s.timeRange);
  const { data, isLoading } = useRunningBalance();
  const palette = useChartPalette();

  const points = data?.points ?? [];
  const labels = useMemo(() => points.map((p) => shortDate(p.date)), [points]);

  return (
    <section className="card dash-grid__wide">
      <div className="card__head">
        <h3>Balance over time</h3>
        <span className="pill">{timeRangeLabel(timeRange).toLowerCase()}</span>
      </div>
      <div className="card__body">
        <p className="muted card__blurb">
          Cumulative net cash flow across the selected range — hover a point for that day's in/out
          split. Transfers between your own accounts don't move this line; only real income and
          spending do.
        </p>
        {isLoading && <div className="empty">Tallying…</div>}
        {!isLoading && points.length === 0 && <div className="empty">No entries in this range.</div>}
        {points.length > 0 && (
          <LineChart
            labels={labels}
            series={[
              {
                label: "Balance",
                color: palette.credit,
                fill: true,
                data: points.map((p) => Number(p.balance)),
              },
            ]}
            valueFormatter={moneyShort}
            height={220}
            tooltipLabel={({ value, index }) => {
              const p = points[index];
              const lines = [`Balance: ${money(value)}`];
              if (p) lines.push(`In ${money(p.income)} · Out ${money(p.expense)}`);
              return lines;
            }}
          />
        )}
      </div>
    </section>
  );
}

function MonthlyCard() {
  const { data } = useMonthly();
  return (
    <section className="card dash-grid__wide">
      <div className="card__head">
        <h3>Month by month</h3>
        <span className="eyebrow">income · expense · net</span>
      </div>
      <div className="card__body">
        <p className="muted card__blurb">
          Bars show what came in and went out each month; the line traces the net — above zero and
          the loaf is rising.
        </p>
        <div style={{ height: 260 }}>
          <BarChart series={data?.series ?? []} />
        </div>
      </div>
    </section>
  );
}

export function Dashboard() {
  const { data, isLoading, isError, error } = useDashboard();

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">01 · The books</span>
        <h1>Where the dough goes</h1>
        <p>
          A running balance of what comes in and what goes out — with plain-spoken notes on how
          you're tracking. Adjust the range and account up top; every figure follows.
        </p>
      </div>

      {isLoading && <div className="empty">Tallying the ledger…</div>}
      {isError && (
        <div className="empty empty--error">Couldn't load the summary: {String(error)}</div>
      )}

      {data && (
        <div className="grid dash-grid">
          {/* Hero: the one figure on this page that gets the bold treatment */}
          <HighlightCard title="Balance" eyebrow={<span className="pill">{data.currency}</span>}>
            <table className="ledger balance__table">
              <tbody>
                <tr>
                  <td>Credits · money in</td>
                  <td className="num">
                    <Money value={data.total_income} sign="credit" />
                  </td>
                </tr>
                <tr>
                  <td>Debits · money out</td>
                  <td className="num">
                    <Money value={`-${data.total_expense}`} sign="debit" />
                  </td>
                </tr>
                <tr className="total">
                  <td>Net cashflow</td>
                  <td className="num">
                    <Money
                      value={data.net_cashflow}
                      sign={Number(data.net_cashflow) >= 0 ? "credit" : "debit"}
                    />
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="highlight-card__note">
              What's left after everything else — your dough for the next stretch.
            </p>
          </HighlightCard>

          <section className="stat-col">
            <div className="card stat">
              <span className="eyebrow">Savings rate</span>
              <div className="stat__value fig">{percent(data.savings_rate, 0)}</div>
              <span className="stat__sub muted">of everything that came in, still yours</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Net worth</span>
              <div className="stat__value">
                <Money
                  value={data.net_worth}
                  sign={Number(data.net_worth) >= 0 ? "credit" : "debit"}
                />
              </div>
              <span className="stat__sub muted">assets less liabilities, today</span>
            </div>
            <div className="card stat">
              <span className="eyebrow">Moved, not spent</span>
              <div className="stat__value">
                <Money value={data.transfer_volume} />
              </div>
              <span className="stat__sub muted">transfers between your own accounts</span>
            </div>
          </section>

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

          <section className="card">
            <div className="card__head">
              <h3>Heaviest expenses</h3>
            </div>
            <div className="card__body">
              {data.top_expense_accounts.length === 0 ? (
                <div className="empty">No expenses in range.</div>
              ) : (
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th className="num">Spent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_expense_accounts.map((c) => (
                      <tr key={c.account_id}>
                        <td>
                          <span className="fig col-code">{c.code}</span> {c.account_name}
                          {c.is_statutory && <span className="pill pill--sm">statutory</span>}
                        </td>
                        <td className="num">
                          <Money value={c.total} sign="debit" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          <BalanceTrendCard />
          <MonthlyCard />
        </div>
      )}
    </div>
  );
}
