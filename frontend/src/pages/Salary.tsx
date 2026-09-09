import { useEffect, useMemo, useState } from "react";
import {
  useAccounts,
  useActiveSalary,
  useCalculate,
  useDeleteProfile,
  useMeta,
  usePostPayslip,
  useSalaryProfiles,
  useSaveProfile,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { localISODateTime, money, percent } from "@/lib/format";
import type { Breakdown, PayPeriod } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  gross: "Gross",
  social: "Contribution",
  tax: "Tax",
  net: "Take-home",
  info: "For reference",
};

function BreakdownTable({ breakdown }: { breakdown: Breakdown }) {
  const monthly = breakdown.pay_period === "monthly";
  return (
    <table className="ledger">
      <thead>
        <tr>
          <th>Line</th>
          <th className="num">{monthly ? "Per month" : "Per year"}</th>
          <th className="num">Annual</th>
        </tr>
      </thead>
      <tbody>
        {breakdown.items.map((item) => (
          <tr key={item.key} className={item.kind === "net" ? "total" : undefined}>
            <td>
              {item.label}
              <span className="muted"> · {KIND_LABEL[item.kind]}</span>
            </td>
            <td className="num">
              <Money
                value={item.amount_period}
                sign={item.kind === "gross" || item.kind === "net" ? "credit" : "debit"}
              />
            </td>
            <td className="num muted fig">{money(item.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Posts the active payslip to the ledger as one balanced multi-line entry —
 * gross credited to income, each withholding debited, the remainder banked. */
function PostToLedger({ profileId }: { profileId: number }) {
  const { data: accounts } = useAccounts({ type: "asset" });
  const post = usePostPayslip();
  const [depositId, setDepositId] = useState<number | "">("");
  const [when, setWhen] = useState(localISODateTime(new Date()));

  const result = post.data;

  return (
    <div className="post-payslip">
      <div className="form-row">
        <label className="field">
          <span className="eyebrow">Net pay lands in</span>
          <select
            value={depositId}
            onChange={(e) => setDepositId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">Select an account…</option>
            {accounts?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} · {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="eyebrow">Dated</span>
          <input
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
          />
        </label>
        <button
          className="btn btn--primary"
          disabled={depositId === "" || post.isPending}
          onClick={() =>
            post.mutate({
              id: profileId,
              deposit_account_id: Number(depositId),
              occurred_at: when,
            })
          }
        >
          {post.isPending ? "Posting…" : "Post to ledger"}
        </button>
      </div>
      {result && (
        <div className={`callout ${result.created ? "callout--good" : ""}`}>
          {result.created
            ? `Posted as entry #${result.entry.id} — ${result.entry.lines.length} lines, balanced.`
            : `Already posted as entry #${result.entry.id}. A payslip posts once.`}
        </div>
      )}
      {post.isError && <div className="empty empty--error">{String(post.error)}</div>}
    </div>
  );
}

export function Salary() {
  const { data: meta } = useMeta();
  const { data: active } = useActiveSalary();
  const { data: profiles } = useSalaryProfiles();
  const calculate = useCalculate();
  const save = useSaveProfile();
  const remove = useDeleteProfile();

  const [gross, setGross] = useState("");
  const [payPeriod, setPayPeriod] = useState<PayPeriod>("monthly");
  const [label, setLabel] = useState("Day job");
  const [seeded, setSeeded] = useState(false);

  // Adopt the active profile's inputs once, so the form and the breakdown it
  // shows describe the same salary. Without this the box holds a placeholder
  // while the table below reports the saved profile — two different numbers
  // on screen claiming to be the same thing.
  useEffect(() => {
    if (seeded || !active) return;
    setGross(String(Number(active.gross_amount)));
    setPayPeriod(active.pay_period);
    setLabel(active.label);
    setSeeded(true);
  }, [active, seeded]);

  const preview = calculate.data;
  const shown = preview ?? active?.breakdown;

  const takeHome = useMemo(() => {
    if (!shown) return null;
    const g = Number(shown.gross_period);
    return g ? Number(shown.net_period) / g : null;
  }, [shown]);

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">02 · Salary</span>
        <h1>What survives to net</h1>
        <p>
          {meta ? `${meta.modelled_as} — ${meta.tax_year} rules. ` : ""}
          TRAIN brackets applied after SSS, PhilHealth and Pag-IBIG, which are deductible.
          Planning-grade approximations, not tax-filing figures.
        </p>
      </div>

      <div className="grid analytics-cols">
        <section className="card">
          <div className="card__head">
            <h3>Calculator</h3>
            <span className="pill">PHP</span>
          </div>
          <div className="card__body">
            <form
              className="form-row"
              onSubmit={(e) => {
                e.preventDefault();
                calculate.mutate({ gross_amount: gross, pay_period: payPeriod });
              }}
            >
              <label className="field">
                <span className="eyebrow">Gross</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={gross}
                  onChange={(e) => setGross(e.target.value)}
                  placeholder="42000"
                  required
                />
              </label>
              <label className="field">
                <span className="eyebrow">Period</span>
                <select
                  value={payPeriod}
                  onChange={(e) => setPayPeriod(e.target.value as PayPeriod)}
                >
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual</option>
                </select>
              </label>
              <button className="btn btn--primary">Calculate</button>
            </form>

            {shown && (
              <>
                <div className="stat-grid stat-grid--tight">
                  <div className="stat">
                    <span className="eyebrow">Take-home</span>
                    <div className="stat__value">
                      <Money value={shown.net_period} sign="credit" />
                    </div>
                  </div>
                  <div className="stat">
                    <span className="eyebrow">Deducted</span>
                    <div className="stat__value">
                      <Money
                        value={(Number(shown.gross_period) - Number(shown.net_period)).toFixed(2)}
                        sign="debit"
                      />
                    </div>
                  </div>
                  <div className="stat">
                    <span className="eyebrow">You keep</span>
                    <div className="stat__value fig">
                      {takeHome != null ? percent(takeHome, 1) : "—"}
                    </div>
                  </div>
                </div>
                <BreakdownTable breakdown={shown} />
              </>
            )}

            {preview && (
              <form
                className="form-row"
                style={{ marginTop: 16 }}
                onSubmit={(e) => {
                  e.preventDefault();
                  save.mutate({ label, gross_amount: gross, pay_period: payPeriod });
                }}
              >
                <label className="field field--wide">
                  <span className="eyebrow">Save as</span>
                  <input value={label} onChange={(e) => setLabel(e.target.value)} />
                </label>
                <button className="btn" disabled={save.isPending}>
                  {save.isPending ? "Saving…" : "Save profile"}
                </button>
              </form>
            )}
          </div>
        </section>

        <div className="grid" style={{ gap: 20 }}>
          <section className="card">
            <div className="card__head">
              <h3>Post the payslip</h3>
              <span className="eyebrow">F1 → F2</span>
            </div>
            <div className="card__body">
              <p className="muted card__blurb">
                A payslip is not one movement but several — gross earned, each withholding taken,
                the remainder banked. One balanced entry says all of it, and every figure then
                flows into the ledger, the budgets, and the analytics at once.
              </p>
              {active ? (
                <PostToLedger profileId={active.id} />
              ) : (
                <div className="empty">Save a profile first, then post it.</div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card__head">
              <h3>Saved profiles</h3>
            </div>
            <div className="card__body">
              {!profiles?.length ? (
                <div className="empty">No profiles saved yet.</div>
              ) : (
                <table className="ledger">
                  <tbody>
                    {profiles.map((p) => (
                      <tr key={p.id}>
                        <td>
                          {p.label}
                          {p.is_active && <span className="pill pill--sm">active</span>}
                        </td>
                        <td className="num">
                          <Money value={p.breakdown.net_period} sign="credit" />
                        </td>
                        <td className="num">
                          <button
                            className="btn btn--ghost btn--sm"
                            onClick={() => remove.mutate(p.id)}
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
      </div>
    </div>
  );
}
