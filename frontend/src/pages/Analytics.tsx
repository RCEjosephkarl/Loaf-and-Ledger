import { useEffect, useMemo, useRef, useState } from "react";
import {
  monthsForRange,
  useAnalyticsOverview,
  useEarnings,
  useMonthly,
  useMonthlyByAccount,
  usePreviousAnalyticsOverview,
  useRebuildWarehouse,
  useRunningBalance,
  useWarehouseStatus,
} from "@/api/queries";
import { BarChart } from "@/components/BarChart";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { StackedBarChart } from "@/components/StackedBarChart";
import { WaterfallChart, type WaterfallStep } from "@/components/WaterfallChart";
import { useChartPalette } from "@/lib/chartColors";
import { money, moneyShort, percent, shortDate, signedPercent } from "@/lib/format";
import { rangeBounds, timeRangeLabel, useFilters } from "@/store/filters";
import type { AccountTotal } from "@/lib/types";

/* ============================================================
   The Analytics page is a four-act argument, not a wall of charts.
   Each act states a claim in prose with the real number set inline,
   then shows the chart that proves it. The prose carries the
   argument; the charts are evidence.
   ============================================================ */

const ACTS = [
  { id: "earned", numeral: "I", title: "What came in" },
  { id: "spent", numeral: "II", title: "Where it went" },
  { id: "left", numeral: "III", title: "What's left" },
  { id: "means", numeral: "IV", title: "What it means" },
] as const;

/** A number set in the display serif, inline in a sentence. */
function Fig({ children, tone }: { children: React.ReactNode; tone?: "credit" | "debit" }) {
  return <strong className={`lede-fig ${tone ? `lede-fig--${tone}` : ""}`}>{children}</strong>;
}

function ActNav({ active }: { active: string }) {
  return (
    <nav className="act-nav" aria-label="Sections">
      {ACTS.map((act) => (
        <a
          key={act.id}
          href={`#${act.id}`}
          className={`act-nav__item ${active === act.id ? "act-nav__item--on" : ""}`}
        >
          <span className="act-nav__numeral">{act.numeral}</span>
          <span>{act.title}</span>
        </a>
      ))}
    </nav>
  );
}

function Act({
  id,
  numeral,
  title,
  lede,
  children,
}: {
  id: string;
  numeral: string;
  title: string;
  lede: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="act" id={id}>
      <header className="act__head">
        <span className="act__numeral" aria-hidden>
          {numeral}
        </span>
        <div>
          <h2 className="act__title">{title}</h2>
          <p className="act__lede">{lede}</p>
        </div>
      </header>
      <div className="act__body">{children}</div>
    </section>
  );
}

/** Ranked horizontal bars — not a pie. Magnitude comparison is what a reader
 * actually does here, and length beats angle at it every time. */
function RankedBars({
  rows,
  total,
  deltas,
}: {
  rows: AccountTotal[];
  total: number;
  deltas?: Map<string, number | null>;
}) {
  if (!rows.length) return <div className="empty">Nothing in this range.</div>;
  const max = Math.max(...rows.map((r) => Number(r.total)), 1);

  return (
    <table className="ledger ranked">
      <thead>
        <tr>
          <th>Account</th>
          <th className="ranked__barcol">Share</th>
          <th className="num">Amount</th>
          {deltas && <th className="num">Δ vs prior</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const value = Number(row.total);
          const change = deltas?.get(row.account_name) ?? null;
          return (
            <tr key={row.account_id}>
              <td>
                <span className="fig col-code">{row.code}</span> {row.account_name}
                {row.is_statutory && <span className="pill pill--sm">statutory</span>}
              </td>
              <td className="ranked__barcol">
                <div className="ranked__track">
                  <div
                    className={`ranked__fill ${row.is_statutory ? "ranked__fill--statutory" : ""}`}
                    style={{ width: `${(value / max) * 100}%` }}
                  />
                </div>
                <span className="ranked__pct muted fig">
                  {total > 0 ? percent(value / total, 0) : "—"}
                </span>
              </td>
              <td className="num">
                <Money value={row.total} sign="debit" />
              </td>
              {deltas && (
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
  );
}

/** Warehouse drift, surfaced only when there is any. Write-through keeps the
 * two stores in step; this is the honest admission that it can miss. */
function StaleBanner() {
  const { data: status } = useWarehouseStatus();
  const rebuild = useRebuildWarehouse();
  if (!status || status.ok) return null;

  return (
    <div className="callout callout--warn">
      <div>
        <strong>Analytics are behind the ledger.</strong>{" "}
        {status.drift !== 0
          ? `${Math.abs(status.drift)} journal line${Math.abs(status.drift) === 1 ? "" : "s"} ${
              status.drift > 0 ? "not yet loaded" : "left over"
            } in the warehouse.`
          : status.note}
      </div>
      <button className="btn" onClick={() => rebuild.mutate()} disabled={rebuild.isPending}>
        {rebuild.isPending ? "Rebuilding…" : "Rebuild warehouse"}
      </button>
    </div>
  );
}

export function Analytics() {
  const timeRange = useFilters((s) => s.timeRange);
  const { data: overview, isLoading } = useAnalyticsOverview();
  const { data: prev } = usePreviousAnalyticsOverview();
  const { data: earnings } = useEarnings();
  const { data: monthly } = useMonthly();
  const { data: mix } = useMonthlyByAccount(monthsForRange(timeRange));
  const { data: balance } = useRunningBalance();
  const palette = useChartPalette();

  const [activeAct, setActiveAct] = useState<string>("earned");
  const rootRef = useRef<HTMLDivElement>(null);

  // Light the act-nav entry for whichever act is nearest the top of the
  // viewport — a scroll narrative needs to say where you are.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActiveAct(visible.target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );
    ACTS.forEach((act) => {
      const el = document.getElementById(act.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [isLoading]);

  const income = Number(overview?.total_income ?? 0);
  const expense = Number(overview?.total_expense ?? 0);
  const net = Number(overview?.net_cashflow ?? 0);
  const transfers = Number(overview?.transfer_volume ?? 0);

  const expenseRows = useMemo(
    () =>
      (overview?.accounts ?? [])
        .filter((a) => a.flow_class === "outflow")
        .sort((a, b) => Number(b.total) - Number(a.total)),
    [overview],
  );
  const incomeRows = useMemo(
    () =>
      (overview?.accounts ?? [])
        .filter((a) => a.flow_class === "inflow")
        .sort((a, b) => Number(b.total) - Number(a.total)),
    [overview],
  );

  const prevDeltas = useMemo(() => {
    const map = new Map<string, number | null>();
    const prior = new Map<string, number>();
    prev?.accounts
      .filter((a) => a.flow_class === "outflow")
      .forEach((a) => prior.set(a.account_name, Number(a.total)));
    expenseRows.forEach((row) => {
      const before = prior.get(row.account_name);
      map.set(row.account_name, before && before > 0 ? (Number(row.total) - before) / before : null);
    });
    return map;
  }, [prev, expenseRows]);

  const statutory = expenseRows.filter((r) => r.is_statutory);
  const statutoryTotal = statutory.reduce((s, r) => s + Number(r.total), 0);
  const topExpense = expenseRows[0];

  /** Gross → each withholding → net, as floating bars. */
  const waterfall = useMemo<WaterfallStep[]>(() => {
    if (!earnings?.items.length) return [];
    const gross = earnings.items.find((i) => i.kind === "gross");
    const net = earnings.items.find((i) => i.kind === "net");
    const deductions = earnings.items
      .filter((i) => i.kind === "tax" || i.kind === "social")
      .sort((a, b) => Number(b.amount) - Number(a.amount));

    return [
      ...(gross ? [{ label: gross.label, delta: Number(gross.amount), isTotal: true }] : []),
      ...deductions.map((i) => ({ label: i.label, delta: -Number(i.amount) })),
      ...(net ? [{ label: net.label, delta: Number(net.amount), isTotal: true }] : []),
    ];
  }, [earnings]);

  /** Average spend per hour/day/week over the range, and how long cash lasts. */
  const burn = useMemo(() => {
    const { start, end } = rangeBounds(timeRange);
    if (!start || !end || !expense) return null;
    const days =
      Math.round((new Date(end).getTime() - new Date(start).getTime()) / 86_400_000) + 1;
    const perDay = expense / Math.max(days, 1);
    const closing = balance?.points.length
      ? Number(balance.points[balance.points.length - 1].cumulative_balance)
      : 0;
    return {
      perDay,
      perWeek: perDay * 7,
      perMonth: perDay * 30.44,
      runway: perDay > 0 ? Math.floor(Math.max(closing, 0) / perDay) : null,
      closing,
    };
  }, [expense, timeRange, balance]);

  const points = balance?.points ?? [];
  const takeHomeRate = Number(earnings?.take_home_rate ?? 0);

  return (
    <div className="analytics" ref={rootRef}>
      <div className="page-head">
        <span className="eyebrow">06 · Analytics</span>
        <h1>The story your money tells</h1>
        <p>
          Four questions, in the order they matter: what came in, where it went, what's left, and
          what that means. Every figure below is read from the analytics warehouse — the same
          numbers the ledger holds, aggregated for reading rather than writing.
        </p>
      </div>

      <StaleBanner />

      {isLoading && <div className="empty">Crunching…</div>}

      {overview && (
        <div className="analytics__layout">
          <ActNav active={activeAct} />

          <div className="analytics__acts">
            {/* ---------------------------------------------- ACT I */}
            <Act
              id="earned"
              numeral="I"
              title="What came in"
              lede={
                earnings && Number(earnings.gross) > 0 ? (
                  <>
                    Every payday, <Fig>{money(earnings.gross)}</Fig> is earned and{" "}
                    <Fig tone="credit">{money(earnings.net)}</Fig> reaches your account —{" "}
                    <Fig>{percent(takeHomeRate, 1)}</Fig> of gross. The rest goes to SSS,
                    PhilHealth, Pag-IBIG and the BIR before you ever see it. Across{" "}
                    {timeRangeLabel(timeRange).toLowerCase()}, <Fig tone="credit">{money(income)}</Fig>{" "}
                    came in all told.
                  </>
                ) : (
                  <>
                    <Fig tone="credit">{money(income)}</Fig> came in over{" "}
                    {timeRangeLabel(timeRange).toLowerCase()}. Save a salary profile to see the
                    gross-to-net breakdown behind it.
                  </>
                )
              }
            >
              <div className="grid analytics-cols">
                <section className="card">
                  <div className="card__head">
                    <h3>Gross to net</h3>
                    <span className="eyebrow">
                      {earnings?.pay_period === "annual" ? "per year" : "per month"}
                    </span>
                  </div>
                  <div className="card__body">
                    <p className="muted card__blurb">
                      Each bar hangs from where the last one ended, so you can watch every
                      withholding take its bite rather than reading five numbers and doing the
                      subtraction yourself.
                    </p>
                    <WaterfallChart steps={waterfall} />
                  </div>
                </section>

                <section className="card">
                  <div className="card__head">
                    <h3>Every source of income</h3>
                    <span className="eyebrow">{timeRangeLabel(timeRange).toLowerCase()}</span>
                  </div>
                  <div className="card__body">
                    {!incomeRows.length ? (
                      <div className="empty">No income recorded in this range.</div>
                    ) : (
                      <table className="ledger">
                        <tbody>
                          {incomeRows.map((row) => (
                            <tr key={row.account_id}>
                              <td>
                                <span className="fig col-code">{row.code}</span> {row.account_name}
                              </td>
                              <td className="num muted fig">
                                {income > 0 ? percent(Number(row.total) / income, 0) : "—"}
                              </td>
                              <td className="num">
                                <Money value={row.total} sign="credit" />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="total">
                            <td colSpan={2}>Total in</td>
                            <td className="num">
                              <Money value={income.toFixed(2)} sign="credit" />
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    )}
                  </div>
                </section>
              </div>
            </Act>

            {/* --------------------------------------------- ACT II */}
            <Act
              id="spent"
              numeral="II"
              title="Where it went"
              lede={
                topExpense ? (
                  <>
                    <Fig tone="debit">{money(expense)}</Fig> went out.{" "}
                    <Fig>{topExpense.account_name}</Fig> took the largest share at{" "}
                    <Fig>{percent(Number(topExpense.total) / expense, 0)}</Fig>
                    {statutoryTotal > 0 && (
                      <>
                        , and <Fig>{money(statutoryTotal)}</Fig> was never discretionary at all —
                        it was withheld
                      </>
                    )}
                    .
                    {transfers > 0 && (
                      <>
                        {" "}
                        A further <Fig>{money(transfers)}</Fig> moved between your own accounts;
                        that is saving, not spending, and none of it is counted here.
                      </>
                    )}
                  </>
                ) : (
                  <>Nothing spent in this range.</>
                )
              }
            >
              <div className="grid" style={{ gap: 20 }}>
                <section className="card">
                  <div className="card__head">
                    <h3>Expense by account</h3>
                    <span className="eyebrow">
                      {timeRange !== "all" ? "Δ compares the prior period of equal length" : "all time"}
                    </span>
                  </div>
                  <div className="card__body">
                    <RankedBars
                      rows={expenseRows}
                      total={expense}
                      deltas={timeRange !== "all" ? prevDeltas : undefined}
                    />
                  </div>
                </section>

                <section className="card">
                  <div className="card__head">
                    <h3>The mix, month over month</h3>
                    <span className="eyebrow">stacked by account</span>
                  </div>
                  <div className="card__body">
                    <p className="muted card__blurb">
                      The top eight accounts by spend keep their own color; the rest fold into
                      "Other". Colors follow the account, so filtering never repaints the survivors.
                    </p>
                    <StackedBarChart months={mix?.months ?? []} series={mix?.series ?? []} />
                  </div>
                </section>
              </div>
            </Act>

            {/* -------------------------------------------- ACT III */}
            <Act
              id="left"
              numeral="III"
              title="What's left"
              lede={
                <>
                  {timeRange === "all"
                    ? "Across everything on record, you are "
                    : `You ended ${timeRangeLabel(timeRange).toLowerCase()} `}
                  <Fig tone={net >= 0 ? "credit" : "debit"}>
                    {money(Math.abs(net))} {net >= 0 ? "ahead" : "behind"}
                  </Fig>
                  .
                  {burn && (
                    <>
                      {" "}
                      At your current burn of <Fig>{money(burn.perDay)}</Fig> a day
                      {burn.runway != null && (
                        <>
                          , the cash you're holding covers <Fig>{burn.runway}</Fig> more{" "}
                          {burn.runway === 1 ? "day" : "days"}
                        </>
                      )}
                      .
                    </>
                  )}
                </>
              }
            >
              <div className="grid analytics-cols">
                <section className="card">
                  <div className="card__head">
                    <h3>Cash flow</h3>
                    <span className="eyebrow">cumulative</span>
                  </div>
                  <div className="card__body">
                    {points.length === 0 ? (
                      <div className="empty">No entries in this range.</div>
                    ) : (
                      <LineChart
                        labels={points.map((p) => shortDate(p.date))}
                        series={[
                          {
                            label: "Running balance",
                            color: palette.credit,
                            fill: true,
                            data: points.map((p) => Number(p.balance)),
                          },
                        ]}
                        valueFormatter={moneyShort}
                        height={260}
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

                <section className="card">
                  <div className="card__head">
                    <h3>Burn rate</h3>
                    <span className="eyebrow">average outgoings</span>
                  </div>
                  <div className="card__body">
                    {!burn ? (
                      <div className="empty">Pick a specific range (not "All") to see a burn rate.</div>
                    ) : (
                      <table className="ledger">
                        <tbody>
                          <tr>
                            <td>Per day</td>
                            <td className="num">
                              <Money value={burn.perDay.toFixed(2)} sign="debit" />
                            </td>
                          </tr>
                          <tr>
                            <td>Per week</td>
                            <td className="num">
                              <Money value={burn.perWeek.toFixed(2)} sign="debit" />
                            </td>
                          </tr>
                          <tr>
                            <td>Per month</td>
                            <td className="num">
                              <Money value={burn.perMonth.toFixed(2)} sign="debit" />
                            </td>
                          </tr>
                          <tr className="total">
                            <td>Runway on current cash</td>
                            <td className="num fig">
                              {burn.runway != null ? `${burn.runway} days` : "—"}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    )}
                  </div>
                </section>
              </div>
            </Act>

            {/* --------------------------------------------- ACT IV */}
            <Act
              id="means"
              numeral="IV"
              title="What it means"
              lede={
                <>
                  Of everything that came in, you still hold{" "}
                  <Fig tone={net >= 0 ? "credit" : "debit"}>{percent(overview.savings_rate, 0)}</Fig>
                  . Every note below is a plain comparison you could redo by hand — no model,
                  no black box.
                </>
              }
            >
              <div className="grid" style={{ gap: 20 }}>
                <section className="card">
                  <div className="card__head">
                    <h3>Month by month</h3>
                    <span className="eyebrow">income · expense · net</span>
                  </div>
                  <div className="card__body">
                    <div style={{ height: 280 }}>
                      <BarChart series={monthly?.series ?? []} />
                    </div>
                  </div>
                </section>

                <section className="card">
                  <div className="card__head">
                    <h3>The figures behind the story</h3>
                    <span className="eyebrow">{timeRangeLabel(timeRange).toLowerCase()}</span>
                  </div>
                  <div className="card__body">
                    <table className="ledger">
                      <tbody>
                        <tr>
                          <td>Total in</td>
                          <td className="num">
                            <Money value={overview.total_income} sign="credit" />
                          </td>
                        </tr>
                        <tr>
                          <td>Total out</td>
                          <td className="num">
                            <Money value={overview.total_expense} sign="debit" />
                          </td>
                        </tr>
                        <tr>
                          <td>
                            Moved between own accounts
                            <span className="muted"> · not spending</span>
                          </td>
                          <td className="num">
                            <Money value={overview.transfer_volume} />
                          </td>
                        </tr>
                        <tr>
                          <td>
                            Statutory withholdings
                            <span className="muted"> · never discretionary</span>
                          </td>
                          <td className="num">
                            <Money value={statutoryTotal.toFixed(2)} sign="debit" />
                          </td>
                        </tr>
                        <tr>
                          <td>Salary · net per period</td>
                          <td className="num">
                            {overview.salary_net_period ? (
                              <Money value={overview.salary_net_period} sign="credit" />
                            ) : (
                              <span className="muted fig">—</span>
                            )}
                          </td>
                        </tr>
                        <tr className="total">
                          <td>Net cash flow</td>
                          <td className="num">
                            <Money
                              value={overview.net_cashflow}
                              sign={net >= 0 ? "credit" : "debit"}
                            />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            </Act>
          </div>
        </div>
      )}
    </div>
  );
}
