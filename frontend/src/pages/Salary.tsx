import { useEffect, useMemo, useState } from "react";
import {
  useAccounts,
  useActivateProfile,
  useActiveSalary,
  useCalculate,
  useDeleteProfile,
  useMeta,
  usePostPayslip,
  useSalaryProfiles,
  useSaveProfile,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { localISODateTime, money, percent, PAY_PERIOD_LABEL, PER_PERIOD_LABEL } from "@/lib/format";
import type { Breakdown, PayPeriod } from "@/lib/types";
import { InfoNote } from "@/components/InfoNote";

const KIND_LABEL: Record<string, string> = {
  gross: "Gross",
  social: "Contribution",
  tax: "Tax",
  net: "Take-home",
  info: "For reference",
};

function BreakdownTable({ breakdown }: { breakdown: Breakdown }) {
  const gross = Number(breakdown.gross_period);
  return (
    <table className="ledger">
      <thead>
        <tr>
          <th>Line</th>
          <th className="num">{PER_PERIOD_LABEL[breakdown.pay_period]}</th>
          <th className="num">Annual</th>
          <th className="num">% of gross deducted</th>
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
            <td className="num muted fig">
              {gross > 0 && (item.kind === "tax" || item.kind === "social")
                ? percent(Number(item.amount_period) / gross, 2) : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Posts the active payslip to the ledger as one balanced multi-line entry —
 * gross credited to income, each withholding debited, the remainder banked. */
function PostToLedger({ profileId, disabled, onPending }: {
  profileId: number; disabled: boolean; onPending: (pending: boolean) => void;
}) {
  const { data: accounts } = useAccounts({ type: "asset" });
  const post = usePostPayslip();
  const [depositId, setDepositId] = useState<number | "">("");
  const [when, setWhen] = useState(localISODateTime(new Date()));

  const result = post.data;
  useEffect(() => { onPending(post.isPending); }, [post.isPending, onPending]);

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
          disabled={disabled || depositId === "" || post.isPending}
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
  const activate = useActivateProfile();
  const [posting, setPosting] = useState(false);

  const [gross, setGross] = useState("");
  const [payPeriod, setPayPeriod] = useState<PayPeriod>("monthly");
  const [label, setLabel] = useState("Day job");
  const [loadedId, setLoadedId] = useState<number | null>(null);

  // A successful profile switch replaces both the inputs and displayed snapshot.
  useEffect(() => {
    if (!active || active.id === loadedId) return;
    setGross(String(Number(active.gross_amount)));
    setPayPeriod(active.pay_period);
    setLabel(active.label);
    calculate.reset();
    setLoadedId(active.id);
  }, [active, loadedId, calculate.reset]);

  const previewMatches = calculate.data != null &&
    calculate.variables?.gross_amount === gross && calculate.variables?.pay_period === payPeriod;
  const preview = previewMatches ? calculate.data : undefined;
  const inputsMatchActive = active && Number(gross) === Number(active.gross_amount) &&
    payPeriod === active.pay_period;
  const shown = preview ?? (inputsMatchActive ? active.breakdown : undefined);
  const busy = activate.isPending || save.isPending || remove.isPending || posting;

  const takeHome = useMemo(() => {
    if (!shown) return null;
    const g = Number(shown.gross_period);
    return g ? Number(shown.net_period) / g : null;
  }, [shown]);

  return (
    <div>
      <div className="page-head">
        <h1>
          Salary
          <InfoNote label="About salary" lead="What survives to net.">
            <p>
              {meta ? `${meta.modelled_as} — ${meta.tax_year} rules. ` : ""}
              TRAIN brackets applied after SSS, PhilHealth and Pag-IBIG, which are deductible.
              Planning-grade approximations, not tax-filing figures.
            </p>
          </InfoNote>
        </h1>
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
                if (!busy) calculate.mutate({ gross_amount: gross, pay_period: payPeriod });
              }}
            >
              <label className="field">
                <span className="eyebrow">Gross</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  disabled={busy}
                  value={gross}
                  onChange={(e) => setGross(e.target.value)}
                  placeholder="42000"
                  required
                />
              </label>
              <label className="field">
                <span className="eyebrow">Period</span>
                <select
                  disabled={busy}
                  value={payPeriod}
                  onChange={(e) => setPayPeriod(e.target.value as PayPeriod)}
                >
                  <option value="monthly">Monthly</option>
                  <option value="fortnightly">Fortnightly (every 2 weeks)</option>
                  <option value="annual">Annual</option>
                </select>
              </label>
              <button className="btn btn--primary" disabled={busy || calculate.isPending}>
                Calculate
              </button>
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
                  if (!busy && previewMatches) {
                    save.mutate({ label, gross_amount: gross, pay_period: payPeriod });
                  }
                }}
              >
                <label className="field field--wide">
                  <span className="eyebrow">Save as</span>
                  <input value={label} onChange={(e) => setLabel(e.target.value)} />
                </label>
                <button className="btn" disabled={busy || calculate.isPending || !previewMatches}>
                  {save.isPending ? "Saving…" : "Save profile"}
                </button>
              </form>
            )}
            {calculate.isError && <div className="empty empty--error">{String(calculate.error)}</div>}
            {save.isError && <div className="empty empty--error">{String(save.error)}</div>}
          </div>
        </section>

        <div className="grid" style={{ gap: 20 }}>
          <section className="card">
            <div className="card__head">
              <h3>
                Post this payslip to the ledger
                <InfoNote label="About posting a payslip">
                  <p>
                    A payslip is not one movement but several — gross earned, each withholding
                    taken, the remainder banked. One balanced entry says all of it, and every
                    figure then flows into the ledger, the budgets, and the analytics at once.
                  </p>
                </InfoNote>
              </h3>
            </div>
            <div className="card__body">
              {active ? (
                <>
                  <p className="eyebrow">
                    Current profile: {active.label} · {PAY_PERIOD_LABEL[active.pay_period]}
                  </p>
                  <PostToLedger key={active.id} profileId={active.id}
                    disabled={busy} onPending={setPosting} />
                </>
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
                  <thead>
                    <tr>
                      <th>Profile</th>
                      <th>Period</th>
                      <th className="num">Gross salary</th>
                      <th className="num">Net salary</th>
                      <th>Delete</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profiles.map((p) => (
                      <tr key={p.id} className={p.is_active ? "profile-row profile-row--active" : "profile-row"}
                        onClick={() => { if (!busy && !p.is_active) activate.mutate(p.id); }}>
                        <td>
                          <button className="linkish" disabled={busy} aria-pressed={p.is_active}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!p.is_active) activate.mutate(p.id);
                            }}>{p.label}</button>
                          {p.is_active && <span className="pill pill--sm">current</span>}
                        </td>
                        <td>{PAY_PERIOD_LABEL[p.pay_period]}</td>
                        <td className="num"><Money value={p.breakdown.gross_period} /></td>
                        <td className="num">
                          <Money value={p.breakdown.net_period} sign="credit" />
                        </td>
                        <td className="num">
                          <button
                            className="btn btn--ghost btn--sm"
                            aria-label={`Delete ${p.label}`} disabled={busy}
                            onClick={(e) => { e.stopPropagation(); remove.mutate(p.id); }}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {activate.isPending && <p role="status">Switching current profile…</p>}
              {activate.isError && <div className="empty empty--error">{String(activate.error)}</div>}
              {remove.isError && <div className="empty empty--error">{String(remove.error)}</div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
