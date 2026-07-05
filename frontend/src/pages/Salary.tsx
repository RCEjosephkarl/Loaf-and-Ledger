import { useEffect, useMemo, useState } from "react";
import {
  useActivateProfile,
  useActiveSalary,
  useCalculate,
  useDeleteProfile,
  useRegions,
  useSalaryProfiles,
  useSaveProfile,
} from "@/api/queries";
import { Money } from "@/components/Money";
import { percent } from "@/lib/format";
import { useFilters } from "@/store/filters";
import type { Breakdown, PayPeriod, Region } from "@/lib/types";

export function Salary() {
  const globalRegion = useFilters((s) => s.region);
  const { data: regions } = useRegions();
  const { data: active } = useActiveSalary();
  const { data: profiles } = useSalaryProfiles();

  const calc = useCalculate();
  const save = useSaveProfile();
  const activate = useActivateProfile();
  const remove = useDeleteProfile();

  const [region, setRegion] = useState<Region>((globalRegion || "US") as Region);
  const [gross, setGross] = useState("6000");
  const [period, setPeriod] = useState<PayPeriod>("monthly");
  const [label, setLabel] = useState("My salary");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [view, setView] = useState<"period" | "annual">("period");

  // Seed the form from the active profile once it loads.
  useEffect(() => {
    if (active) {
      setRegion(active.region);
      setGross(String(Number(active.gross_amount)));
      setPeriod(active.pay_period);
      setLabel(active.label);
      setBreakdown(active.breakdown);
    }
  }, [active]);

  const runCalc = async () => {
    const b = await calc.mutateAsync({ region, gross_amount: gross, pay_period: period });
    setBreakdown(b);
  };

  const onSave = async () => {
    const saved = await save.mutateAsync({ region, gross_amount: gross, pay_period: period, label });
    setBreakdown(saved.breakdown);
  };

  const currency = breakdown?.currency ?? "USD";
  const scale = (annual: string, per: string) => (view === "annual" ? annual : per);

  const items = useMemo(() => breakdown?.items ?? [], [breakdown]);
  const factor = view === "annual" ? 1 : 12;
  const perItem = (annualAmount: string) =>
    view === "annual" ? annualAmount : String(Number(annualAmount) / factor);

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">02 · Salary</span>
        <h1>Gross in, net out</h1>
        <p>
          Enter your pay and pick a region — the calculator applies that country's statutory income
          tax and social contributions, then persists your active profile for the rest of the app.
        </p>
      </div>

      <div className="grid salary-grid">
        <section className="card">
          <div className="card__head">
            <h3>Your pay</h3>
          </div>
          <div className="card__body stack" style={{ gap: 16 }}>
            <div className="field">
              <label htmlFor="label">Label</label>
              <input id="label" value={label} onChange={(e) => setLabel(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="region">Region</label>
              <select id="region" value={region} onChange={(e) => setRegion(e.target.value as Region)}>
                {regions?.map((r) => (
                  <option key={r.region} value={r.region}>
                    {r.region} — {r.modelled_as}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="gross">Gross amount</label>
              <input
                id="gross"
                className="fig"
                inputMode="decimal"
                value={gross}
                onChange={(e) => setGross(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="period">Pay period</label>
              <select id="period" value={period} onChange={(e) => setPeriod(e.target.value as PayPeriod)}>
                <option value="monthly">Monthly</option>
                <option value="annual">Annual</option>
              </select>
            </div>
            <div className="row" style={{ gap: 10 }}>
              <button className="btn btn--primary" onClick={runCalc} disabled={calc.isPending}>
                {calc.isPending ? "Calculating…" : "Calculate"}
              </button>
              <button className="btn btn--crust" onClick={onSave} disabled={save.isPending}>
                Save &amp; make active
              </button>
            </div>
            {calc.isError && <div className="empty empty--error">{String(calc.error)}</div>}
          </div>
        </section>

        <section className="card">
          <div className="card__head">
            <h3>Breakdown</h3>
            <div className="filterbar__segment">
              <button className={`seg ${view === "period" ? "seg--on" : ""}`} onClick={() => setView("period")}>
                Per period
              </button>
              <button className={`seg ${view === "annual" ? "seg--on" : ""}`} onClick={() => setView("annual")}>
                Annual
              </button>
            </div>
          </div>
          <div className="card__body">
            {!breakdown ? (
              <div className="empty">Enter your pay and hit Calculate.</div>
            ) : (
              <>
                <table className="ledger">
                  <tbody>
                    {items
                      .filter((i) => i.kind !== "net")
                      .map((i) => (
                        <tr key={i.key}>
                          <td>
                            {i.label}
                            {i.kind === "info" && <span className="pill pill--statutory" style={{ marginLeft: 8 }}>employer</span>}
                            {i.kind === "social" && <span className="pill pill--statutory" style={{ marginLeft: 8 }}>statutory</span>}
                          </td>
                          <td className="num">
                            <Money
                              value={i.kind === "gross" || i.kind === "info" ? perItem(i.amount) : `-${perItem(i.amount)}`}
                              currency={currency}
                              sign={i.kind === "gross" || i.kind === "info" ? "plain" : "debit"}
                            />
                          </td>
                        </tr>
                      ))}
                    <tr className="total">
                      <td>Net take-home</td>
                      <td className="num">
                        <Money value={scale(breakdown.net_annual, breakdown.net_period)} currency={currency} sign="credit" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div className="breakdown-foot">
                  <span className="pill">Effective rate {percent(breakdown.effective_rate, 1)}</span>
                  <span className="pill">Tax year {breakdown.tax_year}</span>
                  <span className="muted" style={{ fontSize: 12 }}>
                    Planning estimate — not tax-filing advice.
                  </span>
                </div>
              </>
            )}
          </div>
        </section>
      </div>

      <section className="card" style={{ marginTop: 20 }}>
        <div className="card__head">
          <h3>Saved profiles</h3>
        </div>
        <div className="card__body">
          {!profiles?.length ? (
            <div className="empty">No saved profiles yet.</div>
          ) : (
            <table className="ledger">
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Region</th>
                  <th className="num">Gross</th>
                  <th className="num">Net / yr</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.label} {p.is_active && <span className="pill pill--credit">active</span>}
                    </td>
                    <td>{p.region}</td>
                    <td className="num">
                      <Money value={p.gross_amount} currency={p.currency} />
                    </td>
                    <td className="num">
                      <Money value={p.net_amount} currency={p.currency} sign="credit" />
                    </td>
                    <td className="num">
                      {!p.is_active && (
                        <button className="btn" onClick={() => activate.mutate(p.id)}>
                          Activate
                        </button>
                      )}{" "}
                      <button className="btn" onClick={() => remove.mutate(p.id)}>
                        Delete
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
  );
}
