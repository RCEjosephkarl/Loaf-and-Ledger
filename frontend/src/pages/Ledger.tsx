import { useMemo, useState } from "react";
import {
  useCategories,
  useCreateTransaction,
  useDeleteTransaction,
  useGlobalParams,
  useRunningBalance,
  useTransactionBalances,
  useTransactions,
  useUpdateTransaction,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { exportUrl } from "@/lib/api";
import { CURRENCIES, formatTime, localISODate } from "@/lib/format";
import { useFilters } from "@/store/filters";
import type { Direction, Transaction } from "@/lib/types";

const today = () => localISODate(new Date());
const nowTime = () => new Date().toTimeString().slice(0, 5);

interface EditDraft {
  category_id: number | "";
  amount: string;
  currency: string;
  occurred_on: string;
  occurred_time: string;
  description: string;
}

export function Ledger() {
  const globalCurrency = useFilters((s) => s.currency);
  const params = useGlobalParams();
  const { data: txns, isLoading } = useTransactions();
  const { data: allCats } = useCategories();
  const { data: balances } = useTransactionBalances();
  const { data: globalBalance } = useRunningBalance({ start: null, end: null });
  const { data: periodBalance } = useRunningBalance();
  const create = useCreateTransaction();
  const remove = useDeleteTransaction();
  const update = useUpdateTransaction();

  const [direction, setDirection] = useState<Direction>("outbound");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState(globalCurrency);
  const [occurredOn, setOccurredOn] = useState(today());
  const [occurredTime, setOccurredTime] = useState(nowTime());
  const [description, setDescription] = useState("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);

  const catName = useMemo(() => {
    const m = new Map<number, string>();
    allCats?.forEach((c) => m.set(c.id, c.name));
    return m;
  }, [allCats]);

  const formCats = useMemo(
    () => allCats?.filter((c) => c.direction === direction && !c.statutory) ?? [],
    [allCats, direction],
  );

  const catsFor = (dir: Direction) => allCats?.filter((c) => c.direction === dir && !c.statutory) ?? [];

  const startEdit = (t: Transaction) => {
    setEditingId(t.id);
    setEditDraft({
      category_id: t.category_id,
      amount: t.amount,
      currency: t.currency,
      occurred_on: t.occurred_on,
      occurred_time: t.occurred_time ? t.occurred_time.slice(0, 5) : "",
      description: t.description ?? "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditDraft(null);
  };

  const saveEdit = async (id: number) => {
    if (!editDraft || editDraft.category_id === "" || !editDraft.amount) return;
    await update.mutateAsync({
      id,
      category_id: Number(editDraft.category_id),
      amount: editDraft.amount,
      currency: editDraft.currency,
      occurred_on: editDraft.occurred_on,
      occurred_time: editDraft.occurred_time || undefined,
      description: editDraft.description || undefined,
    });
    cancelEdit();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (categoryId === "" || !amount) return;
    await create.mutateAsync({
      direction,
      category_id: Number(categoryId),
      amount,
      currency,
      occurred_on: occurredOn,
      occurred_time: occurredTime || undefined,
      description: description || undefined,
    });
    setAmount("");
    setDescription("");
  };

  const lastBalance = (points: { balance: string }[] | undefined) =>
    points && points.length ? points[points.length - 1].balance : "0";
  const globalBalanceValue = lastBalance(globalBalance?.points);
  const periodBalanceValue = lastBalance(periodBalance?.points);

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">03 · Ledger</span>
        <h1>Every entry, dated and dressed</h1>
        <p>Record money in and out, sort it by category, and export the debit side whenever you need it.</p>
      </div>

      <section className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="eyebrow">Global balance</span>
          <div className="stat__value">
            <Money
              value={globalBalanceValue}
              currency={globalCurrency}
              sign={Number(globalBalanceValue) >= 0 ? "credit" : "debit"}
            />
          </div>
          <span className="stat__sub muted">every entry ever recorded</span>
        </div>
        <div className="card stat">
          <span className="eyebrow">Period balance</span>
          <div className="stat__value">
            <Money
              value={periodBalanceValue}
              currency={globalCurrency}
              sign={Number(periodBalanceValue) >= 0 ? "credit" : "debit"}
            />
          </div>
          <span className="stat__sub muted">net change within the current filter</span>
        </div>
      </section>

      <div className="grid ledger-grid">
        <section className="card">
          <div className="card__head">
            <h3>New entry</h3>
          </div>
          <div className="card__body">
            <form className="stack" style={{ gap: 14 }} onSubmit={submit}>
              <div className="filterbar__segment">
                <button
                  type="button"
                  className={`seg ${direction === "outbound" ? "seg--on" : ""}`}
                  onClick={() => {
                    setDirection("outbound");
                    setCategoryId("");
                  }}
                >
                  Debit · out
                </button>
                <button
                  type="button"
                  className={`seg ${direction === "inbound" ? "seg--on" : ""}`}
                  onClick={() => {
                    setDirection("inbound");
                    setCategoryId("");
                  }}
                >
                  Credit · in
                </button>
              </div>
              <div className="field">
                <label>Category</label>
                <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value) || "")}>
                  <option value="">Choose…</option>
                  {formCats.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Amount</label>
                <input className="fig" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required />
              </div>
              <div className="field">
                <label>Currency</label>
                <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  {CURRENCIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="row" style={{ gap: 10 }}>
                <div className="field" style={{ flex: 1 }}>
                  <label>Date</label>
                  <input type="date" value={occurredOn} onChange={(e) => setOccurredOn(e.target.value)} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label>Time</label>
                  <input
                    className="fig"
                    type="time"
                    value={occurredTime}
                    onChange={(e) => setOccurredTime(e.target.value)}
                  />
                </div>
              </div>
              <div className="field">
                <label>Note</label>
                <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" />
              </div>
              <button className="btn btn--primary" type="submit" disabled={create.isPending}>
                {create.isPending ? "Recording…" : "Record entry"}
              </button>
            </form>
          </div>
        </section>

        <section className="card">
          <div className="card__head">
            <h3>Entries</h3>
            <a className="btn" href={exportUrl(params)}>
              ↓ Export expenses CSV
            </a>
          </div>
          <div className="card__body">
            {isLoading ? (
              <div className="empty">Loading…</div>
            ) : !txns?.length ? (
              <div className="empty">No entries in this range. Record one on the left.</div>
            ) : (
              <div className="ledger-scroll">
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Category</th>
                      <th>Type</th>
                      <th className="num">Amount</th>
                      <th className="num">Balance</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {txns.map((t) =>
                      editingId === t.id && editDraft ? (
                        <tr key={t.id} className="ledger-row--editing">
                          <td>
                            <div className="row" style={{ gap: 6 }}>
                              <input
                                type="date"
                                className="fig"
                                value={editDraft.occurred_on}
                                onChange={(e) => setEditDraft({ ...editDraft, occurred_on: e.target.value })}
                              />
                              <input
                                type="time"
                                className="fig"
                                value={editDraft.occurred_time}
                                onChange={(e) => setEditDraft({ ...editDraft, occurred_time: e.target.value })}
                              />
                            </div>
                          </td>
                          <td>
                            <select
                              value={editDraft.category_id}
                              onChange={(e) => setEditDraft({ ...editDraft, category_id: Number(e.target.value) })}
                            >
                              {catsFor(t.direction).map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name}
                                </option>
                              ))}
                            </select>
                            <input
                              style={{ marginTop: 6 }}
                              value={editDraft.description}
                              onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })}
                              placeholder="Note (optional)"
                            />
                          </td>
                          <td>
                            <span
                              className={`pill pill--${t.direction === "inbound" ? "credit" : "debit"}`}
                              title="Direction can't be changed — delete and re-add to flip it"
                            >
                              {t.direction === "inbound" ? "credit" : "debit"}
                            </span>
                          </td>
                          <td className="num">
                            <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                              <input
                                className="fig"
                                style={{ width: 90 }}
                                inputMode="decimal"
                                value={editDraft.amount}
                                onChange={(e) => setEditDraft({ ...editDraft, amount: e.target.value })}
                              />
                              <select
                                style={{ width: 78 }}
                                value={editDraft.currency}
                                onChange={(e) => setEditDraft({ ...editDraft, currency: e.target.value })}
                              >
                                {CURRENCIES.map((c) => (
                                  <option key={c} value={c}>
                                    {c}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </td>
                          <td className="num">
                            {balances?.balances[t.id] !== undefined ? (
                              <Money value={balances.balances[t.id]} currency={globalCurrency} />
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td className="num">
                            <div className="row" style={{ gap: 6 }}>
                              <button className="btn btn--primary" onClick={() => saveEdit(t.id)} disabled={update.isPending}>
                                Save
                              </button>
                              <button className="btn" onClick={cancelEdit}>
                                Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      ) : (
                        <tr key={t.id}>
                          <td className="fig">
                            {t.occurred_on}
                            <div className="muted" style={{ fontSize: 12 }}>{formatTime(t.occurred_time)}</div>
                          </td>
                          <td>
                            {catName.get(t.category_id) ?? "—"}
                            {t.description && <div className="muted" style={{ fontSize: 12 }}>{t.description}</div>}
                          </td>
                          <td>
                            <span className={`pill pill--${t.direction === "inbound" ? "credit" : "debit"}`}>
                              {t.direction === "inbound" ? "credit" : "debit"}
                            </span>
                          </td>
                          <td className="num">
                            <Money
                              value={t.direction === "inbound" ? t.amount : `-${t.amount}`}
                              currency={t.currency}
                              sign={t.direction === "inbound" ? "credit" : "debit"}
                            />
                          </td>
                          <td className="num">
                            {balances?.balances[t.id] !== undefined ? (
                              <Money
                                value={balances.balances[t.id]}
                                currency={globalCurrency}
                                sign={Number(balances.balances[t.id]) >= 0 ? "credit" : "debit"}
                              />
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td className="num">
                            <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                              <button className="btn" onClick={() => startEdit(t)}>
                                Edit
                              </button>
                              <button className="btn" onClick={() => remove.mutate(t.id)}>
                                ✕
                              </button>
                            </div>
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
