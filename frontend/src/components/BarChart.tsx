import { Chart } from "react-chartjs-2";
import { useChartPalette } from "@/lib/chartColors";
import { monthLabel, money } from "@/lib/format";
import type { MonthlyPoint } from "@/lib/types";

/** Combo chart: grouped income-vs-expense bars, one group per month, with
 * the net cash flow traced as an overlaid line (Chart.js mixed dataset). */
export function BarChart({ series, currency }: { series: MonthlyPoint[]; currency: string }) {
  const palette = useChartPalette();
  if (!series.length) return <div className="empty">No monthly data yet.</div>;

  return (
    <div className="chartjs-card">
      <Chart
        type="bar"
        data={{
          labels: series.map((p) => monthLabel(p.month)),
          datasets: [
            {
              type: "bar" as const,
              label: "Income",
              data: series.map((p) => Number(p.income)),
              backgroundColor: palette.green,
              borderRadius: 3,
              maxBarThickness: 22,
            },
            {
              type: "bar" as const,
              label: "Expense",
              data: series.map((p) => Number(p.expense)),
              backgroundColor: palette.crust,
              borderRadius: 3,
              maxBarThickness: 22,
            },
            {
              type: "line" as const,
              label: "Net",
              data: series.map((p) => Number(p.net)),
              borderColor: palette.ink,
              backgroundColor: palette.ink,
              pointRadius: 3,
              pointHoverRadius: 5,
              borderWidth: 2,
              tension: 0.25,
              order: 0,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false }, ticks: { color: palette.muted } },
            y: {
              grid: { color: palette.rule },
              ticks: { color: palette.muted, callback: (v) => money(Number(v), currency) },
            },
          },
          plugins: {
            legend: { position: "bottom", labels: { color: palette.ink } },
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${money(Number(ctx.raw), currency)}`,
              },
            },
          },
        }}
      />
    </div>
  );
}
