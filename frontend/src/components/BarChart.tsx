import { monthLabel, money } from "@/lib/format";
import type { MonthlyPoint } from "@/lib/types";

/** Minimal grouped bar chart: income vs expense per month, themed via CSS vars. */
export function BarChart({ series, currency }: { series: MonthlyPoint[]; currency: string }) {
  if (!series.length) return <div className="empty">No monthly data yet.</div>;

  const H = 170;
  const max = Math.max(...series.flatMap((p) => [Number(p.income), Number(p.expense)]), 1);
  const barH = (v: string) => Math.round((Number(v) / max) * H);

  return (
    <div className="chart">
      <div className="chart__plot" style={{ height: H }}>
        {series.map((p) => (
          <div className="chart__group" key={p.month}>
            <div
              className="chart__bar chart__bar--income"
              style={{ height: barH(p.income) }}
              title={`Income · ${money(p.income, currency)}`}
            />
            <div
              className="chart__bar chart__bar--expense"
              style={{ height: barH(p.expense) }}
              title={`Expense · ${money(p.expense, currency)}`}
            />
          </div>
        ))}
      </div>
      <div className="chart__axis">
        {series.map((p) => (
          <span className="chart__tick" key={p.month}>
            {monthLabel(p.month)}
          </span>
        ))}
      </div>
      <div className="chart__legend">
        <span className="chart__key chart__key--income">Income</span>
        <span className="chart__key chart__key--expense">Expense</span>
      </div>
    </div>
  );
}
