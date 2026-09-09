import { useMemo, useState } from "react";
import {
  toBudgetScope,
  useAccounts,
  useBudgetFund,
  useBudgets,
  useBudgetStatus,
  useDeleteBudget,
  useResetBudgetFund,
  useRunningBalance,
  useSetBudgetFund,
  useUpsertBudget,
} from "@/api/queries";
import { LineChart } from "@/components/LineChart";
import { Money } from "@/components/Money";
import { useChartPalette } from "@/lib/chartColors";
import { money, moneyShort, percent, shortDate } from "@/lib/format";
import { timeRangeLabel, useFilters } from "@/store/filters";
import type { BudgetStatus } from "@/lib/types";

function UtilizationBar({ row }: { row: BudgetStatus }) {
  const pct = Math.min(Number(row.utilization), 1.5);
  const over = row.over_budget;
  return (
    <div className="util">
      <div className="util__track">
        <div
          className={`util__fill ${over ? "util__fill--over" : ""}`}
          style={{ width: `${Math.min(pct, 1) * 100}%` }}
        />
        {over && <div className="util__over" style={{ width: `${Math.min(pct - 1, 0.5) * 100}%` }} />}
      </div>
      <span className={`util__pct fig ${over ? "fig--debit" : ""}`}>
        {percent(row.utilization, 0)}
      </span>
    </div>
  );
}

function FundCard({ scope }: { scope: ReturnType<typeof toBudgetScope> }) {
  const { data: fund } = useBudgetFund(scope);
  const setFund = useSetBudgetFund();
  const resetFund = useResetBudgetFund();
  const [draft, setDraft] = useState("");

  return (
    <section className="card">
      <div className="card__head">
        <h3>Initial fund</h3>
        <span className="eyebrow">{fund?.is_override ? "you set this" : "carried over"}</span>
      </div>
      <div className="card__body">
        <div className="stat__value">
          {fund ? <Money value={fund.amount} sign="credit" /> : <span className="muted">—</span>}
        </div>
        <p className="muted card__blurb">
          What you had going into this period. By default it's the cumulative net cash flow the
          day before it started — override it if your books began mid-stream.
        </p>
        <form
          className="form-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft) setFund.mutate({ scope, amount: draft });
            setDraft("");
          }}
        >
          <label className="field">
            <span className="eyebrow">Override</span>
            <input
              type="number"
              step="0.01"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="0.00"
            />
          </label>
          <button className="btn">Set</button>
          {fund?.is_override && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => resetFund.mutate({ scope })}
            >
              Reset
            </button>
          )}
        </form>
      </div>
    </section>
  );
}

export function Budgets() {
  const timeRange = useFilters((s) => s.timeRange);
  const scope = toBudgetScope(timeRange);
  const { data: rows, isLoading } = useBudgetStatus(scope);
  const { data: budgets } = useBudgets();
  const { data: accounts } = useAccounts({ type: "expense" });
  const { data: balance } = useRunningBalance();
  const upsert = useUpsertBudget();
  const remove = useDeleteBudget();
  const palette = useChartPalette();

  const now = new Date();
  const [accountId, setAccountId] = useState<number | "">("");
  const [limit, setLimit] = useState("");

  const accountName = useMemo(() => {
    const map = new Map<number, string>();
    accounts?.forEach((a) => map.set(a.id, `${a.code} · ${a.name}`));
    return map;
  }, [accounts]);

  const totals = useMemo(() => {
    const limitSum = (rows ?? []).reduce((s, r) => s + Number(r.limit_amount), 0);
    const spentSum = (rows ?? []).reduce((s, r) => s + Number(r.spent), 0);
    return { limitSum, spentSum, over: (rows ?? []).filter((r) => r.over_budget).length };
  }, [rows]);

  const points = balance?.points ?? [];

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">05 · Budgets</span>
        <h1>Limits, and how close you are</h1>
        <p>
          A limit per expense account, per month. Spend is read from the warehouse over the
          selected period — the same figures the Ledger and Analytics show, never a second
          calculation that can disagree.
        </p>
      </div>

      <section className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="eyebrow">Budgeted · {timeRangeLabel(timeRange).toLowerCase()}</span>
          <div className="stat__value">
            <Money value={totals.limitSum.toFixed(2)} />
          </div>
        </div>
        <div className="card stat">
          <span className="eyebrow">Spent against it</span>
          <div className="stat__value">
            <Money value={totals.spentSum.toFixed(2)} sign="debit" />
          </div>
          <span className="stat__sub muted">
            {totals.limitSum > 0 ? percent(totals.spentSum / totals.limitSum, 0) : "—"} of the total
          </span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Over budget</span>
          <div className={`stat__value fig ${totals.over ? "fig--debit" : ""}`}>{totals.over}</div>
          <span className="stat__sub muted">
            of {rows?.length ?? 0} tracked {rows?.length === 1 ? "account" : "accounts"}
          </span>
        </div>
      </section>

      <div className="grid" style={{ gap: 20 }}>
        <section className="card">
          <div className="card__head">
            <h3>Against the limits</h3>
            <span className="pill">{timeRangeLabel(timeRange).toLowerCase()}</span>
          </div>
          <div className="card__body">
            {isLoading && <div className="empty">Adding up…</div>}
            {!isLoading && !rows?.length && (
              <div className="empty">No budgets set for this period yet.</div>
            )}
            {!!rows?.length && (
              <table className="ledger">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th className="num">Limit</th>
                    <th className="num">Spent</th>
                    <th className="num">Left</th>
                    <th className="col-util">Used</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.account_id}>
                      <td>
                        <span className="fig col-code">{r.account_code}</span> {r.account_name}
                      </td>
                      <td className="num muted fig">{money(r.limit_amount)}</td>
                      <td className="num">
                        <Money value={r.spent} sign="debit" />
                      </td>
                      <td className="num">
                        <Money
                          value={r.remaining}
                          sign={Number(r.remaining) >= 0 ? "credit" : "debit"}
                        />
                      </td>
                      <td className="col-util">
                        <UtilizationBar row={r} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <div className="grid analytics-cols">
          <FundCard scope={scope} />

          <section className="card">
            <div className="card__head">
              <h3>Set a limit</h3>
              <span className="eyebrow">expense accounts only</span>
            </div>
            <div className="card__body">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (accountId === "" || !limit) return;
                  upsert.mutate({
                    account_id: Number(accountId),
                    year: now.getFullYear(),
                    month: now.getMonth() + 1,
                    limit_amount: limit,
                  });
                  setLimit("");
                }}
              >
                <div className="form-row">
                  <label className="field field--wide">
                    <span className="eyebrow">Account</span>
                    <select
                      value={accountId}
                      onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
                    >
                      <option value="">Select…</option>
                      {accounts?.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} · {a.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="eyebrow">Monthly limit</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={limit}
                      onChange={(e) => setLimit(e.target.value)}
                      placeholder="0.00"
                    />
                  </label>
                  <button className="btn btn--primary">Set</button>
                </div>
              </form>

              {!!budgets?.length && (
                <table className="ledger" style={{ marginTop: 12 }}>
                  <tbody>
                    {budgets.map((b) => (
                      <tr key={b.id}>
                        <td>{accountName.get(b.account_id) ?? `Account ${b.account_id}`}</td>
                        <td className="muted fig">
                          {b.year}-{String(b.month).padStart(2, "0")}
                        </td>
                        <td className="num">
                          <Money value={b.limit_amount} />
                        </td>
                        <td className="num">
                          <button
                            className="btn btn--ghost btn--sm"
                            onClick={() => remove.mutate(b.id)}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </div>

        <section className="card">
          <div className="card__head">
            <h3>Running balance</h3>
            <span className="eyebrow">{timeRangeLabel(timeRange).toLowerCase()}</span>
          </div>
          <div className="card__body">
            {points.length === 0 ? (
              <div className="empty">No entries in this range.</div>
            ) : (
              <LineChart
                labels={points.map((p) => shortDate(p.date))}
                series={[
                  {
                    label: "Balance",
                    color: palette.credit,
                    fill: true,
                    data: points.map((p) => Number(p.balance)),
                  },
                ]}
                valueFormatter={moneyShort}
                height={200}
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
      </div>
    </div>
  );
}
