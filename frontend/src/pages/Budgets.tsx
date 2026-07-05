import { useMemo, useState } from "react";
import {
  useBudgets,
  useBudgetStatus,
  useCategories,
  useDeleteBudget,
  useUpsertBudget,
} from "@/api/queries";
import { Money, } from "@/components/Money";
import { percent } from "@/lib/format";
import { useFilters } from "@/store/filters";

const now = new Date();

export function Budgets() {
  const currency = useFilters((s) => s.currency);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const { data: outCats } = useCategories("outbound");
  const { data: budgets } = useBudgets();
  const { data: status } = useBudgetStatus(year, month);
  const upsert = useUpsertBudget();
  const removeBudget = useDeleteBudget();

  const [categoryId, setCategoryId] = useState<number | "">("");
  const [limit, setLimit] = useState("");

  const budgetId = useMemo(() => {
    const m = new Map<number, number>();
    budgets?.filter((b) => b.year === year && b.month === month).forEach((b) => m.set(b.category_id, b.id));
    return m;
  }, [budgets, year, month]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (categoryId === "" || !limit) return;
    await upsert.mutateAsync({ category_id: Number(categoryId), year, month, limit_amount: limit, currency });
    setLimit("");
  };

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">04 · Budgets</span>
        <h1>Lines drawn before you spend</h1>
        <p>Set a ceiling per category for the month and watch each one fill as entries land in the ledger.</p>
      </div>

      <div className="row" style={{ gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
        <label className="inline-field">
          <span className="eyebrow">Month</span>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {months.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-field">
          <span className="eyebrow">Year</span>
          <input className="fig" style={{ width: 90 }} value={year} onChange={(e) => setYear(Number(e.target.value) || year)} />
        </label>
      </div>

      <div className="grid budget-grid">
        <section className="card">
          <div className="card__head">
            <h3>Set a limit</h3>
          </div>
          <div className="card__body">
            <form className="stack" style={{ gap: 14 }} onSubmit={submit}>
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
          </div>
        </section>

        <section className="card">
          <div className="card__head">
            <h3>
              {months[month - 1]} {year}
            </h3>
          </div>
          <div className="card__body">
            {!status?.length ? (
              <div className="empty">No budgets set for this month.</div>
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
                        <span className="row" style={{ gap: 10 }}>
                          <span className={Number(s.remaining) < 0 ? "fig fig--debit" : "fig fig--credit"}>
                            <Money value={s.remaining} currency={s.currency} /> left
                          </span>
                          {budgetId.get(s.category_id) && (
                            <button className="btn" onClick={() => removeBudget.mutate(budgetId.get(s.category_id)!)}>
                              ✕
                            </button>
                          )}
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
    </div>
  );
}
