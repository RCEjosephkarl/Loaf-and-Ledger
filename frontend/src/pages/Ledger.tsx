import { useMemo, useState } from "react";
import {
  useCategories,
  useCreateTransaction,
  useDeleteTransaction,
  useGlobalParams,
  useTransactions,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { exportUrl } from "@/lib/api";
import { useFilters } from "@/store/filters";
import type { Direction, Region } from "@/lib/types";

const today = () => new Date().toISOString().slice(0, 10);

export function Ledger() {
  const globalRegion = useFilters((s) => s.region);
  const params = useGlobalParams();
  const { data: txns, isLoading } = useTransactions();
  const { data: allCats } = useCategories();
  const create = useCreateTransaction();
  const remove = useDeleteTransaction();

  const [direction, setDirection] = useState<Direction>("outbound");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [region, setRegion] = useState<Region | "">(globalRegion);
  const [occurredOn, setOccurredOn] = useState(today());
  const [description, setDescription] = useState("");

  const catName = useMemo(() => {
    const m = new Map<number, string>();
    allCats?.forEach((c) => m.set(c.id, c.name));
    return m;
  }, [allCats]);

  const formCats = useMemo(
    () => allCats?.filter((c) => c.direction === direction && !c.statutory) ?? [],
    [allCats, direction],
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (categoryId === "" || !amount) return;
    await create.mutateAsync({
      direction,
      category_id: Number(categoryId),
      amount,
      region: region || undefined,
      occurred_on: occurredOn,
      description: description || undefined,
    });
    setAmount("");
    setDescription("");
  };

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">03 · Ledger</span>
        <h1>Every entry, dated and dressed</h1>
        <p>Record money in and out, sort it by category, and export the debit side whenever you need it.</p>
      </div>

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
                <label>Region (sets currency)</label>
                <select value={region} onChange={(e) => setRegion(e.target.value as Region | "")}>
                  <option value="">Base currency</option>
                  <option value="PH">PH · PHP</option>
                  <option value="US">US · USD</option>
                  <option value="AU">AU · AUD</option>
                  <option value="EU">EU · EUR</option>
                </select>
              </div>
              <div className="field">
                <label>Date</label>
                <input type="date" value={occurredOn} onChange={(e) => setOccurredOn(e.target.value)} />
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
              <div style={{ overflowX: "auto" }}>
                <table className="ledger">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Category</th>
                      <th>Type</th>
                      <th className="num">Amount</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {txns.map((t) => (
                      <tr key={t.id}>
                        <td className="fig">{t.occurred_on}</td>
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
                          <button className="btn" onClick={() => remove.mutate(t.id)}>
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
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
