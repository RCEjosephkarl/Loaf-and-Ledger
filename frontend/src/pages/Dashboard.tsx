import { useDashboard, useFxRates } from "@/api/queries";
import { HighlightCard } from "@/components/HighlightCard";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { exportFxUrl } from "@/lib/api";
import { useChartPalette } from "@/lib/chartColors";
import { percent, shortDate } from "@/lib/format";
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

const FX_LINE_COLORS = ["green", "crust", "warn", "good"] as const;

function fxTooltip(v: { value: number; previousValue: number | null }): string {
  if (v.previousValue == null) return v.value.toFixed(4);
  const abs = v.value - v.previousValue;
  const pct = v.previousValue ? (abs / v.previousValue) * 100 : 0;
  const sign = abs >= 0 ? "+" : "";
  return `${v.value.toFixed(4)}  (${sign}${abs.toFixed(4)}, ${sign}${pct.toFixed(2)}%)`;
}

function FxRatesCard() {
  const currency = useFilters((s) => s.currency);
  const timeRange = useFilters((s) => s.timeRange);
  const { data, isLoading } = useFxRates();
  const palette = useChartPalette();
  const colors = FX_LINE_COLORS.map((k) => palette[k]);

  const labels = data?.series.map((p) => shortDate(p.date)) ?? [];

  return (
    <section className="card dash-grid__wide">
      <div className="card__head">
        <h3>Currency rates · {timeRangeLabel(timeRange).toLowerCase()}</h3>
        <span className="row" style={{ gap: 8 }}>
          {data && (
            <span className={`pill ${data.live ? "pill--credit" : ""}`}>
              {data.live ? "live" : "cached"}
            </span>
          )}
          <a className="btn" href={exportFxUrl({ base: currency })}>
            ↓ Export FX rates CSV
          </a>
        </span>
      </div>
      <div className="card__body">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          How far your {currency} stretches abroad — each currency keeps its own scale below;
          hover a point for the day's move.
        </p>
        {isLoading && <div className="empty">Fetching live rates…</div>}
        {!isLoading && (!data || data.series.length === 0) && (
          <div className="empty">Couldn't reach live rates yet — check your connection.</div>
        )}
        {data && data.series.length > 0 && (
          <div className="fx-grid">
            {data.quotes.map((quote, i) => {
              const values = data.series.map((p) => {
                const v = Number(p.rates[quote]);
                return Number.isNaN(v) ? null : v;
              });
              const latest = [...values].reverse().find((v) => v != null) ?? null;
              const prior = [...values].reverse().filter((v) => v != null)[1] ?? null;
              return (
                <div key={quote} className="fx-mini">
                  <div className="fx-latest__item">
                    <span className="eyebrow" style={{ color: colors[i % colors.length] }}>
                      {data.base} → {quote}
                    </span>
                    <div className="fig fx-latest__value">
                      {latest != null ? fxTooltip({ value: latest, previousValue: prior }) : "—"}
                    </div>
                  </div>
                  <LineChart
                    labels={labels}
                    series={[{ label: quote, color: colors[i % colors.length], data: values, fill: true }]}
                    valueFormatter={(v) => v.toFixed(4)}
                    tooltipLabel={fxTooltip}
                    height={110}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
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
          {/* Hero: balance sheet — the one figure on this page that gets the bold treatment */}
          <HighlightCard title="Balance" eyebrow={<span className="pill">{data.currency}</span>}>
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
            <p className="highlight-card__note">
              What's left after everything else — your dough for the next stretch.
            </p>
          </HighlightCard>

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

          <FxRatesCard />
        </div>
      )}
    </div>
  );
}
