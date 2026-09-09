import { Bar } from "react-chartjs-2";
import { foldToPalette, useChartPalette } from "@/lib/chartColors";
import { monthLabel, money, moneyShort } from "@/lib/format";
import type { MonthlyAccountSeries } from "@/lib/types";

/**
 * Monthly spend stacked by account.
 *
 * Colors are assigned from the fixed categorical order and never cycled: the
 * top eight accounts by total spend take slots 1–8 and everything below folds
 * into a neutral "Other". A 2px surface-colored border separates the stacked
 * segments so adjacent bands stay legible where their hues are close.
 */
export function StackedBarChart({
  months,
  series,
}: {
  months: string[];
  series: MonthlyAccountSeries[];
}) {
  const palette = useChartPalette();
  if (!months.length || !series.length) return <div className="empty">No account data yet.</div>;

  const total = (s: MonthlyAccountSeries) => s.values.reduce((a, v) => a + Number(v), 0);
  const { kept, folded } = foldToPalette(series, total);

  const datasets = kept.map(({ item, color }) => ({
    label: item.account_name,
    data: item.values.map(Number),
    backgroundColor: color(palette),
    borderColor: palette.surface,
    borderWidth: 2,
    borderRadius: 3,
    stack: "spend",
    maxBarThickness: 34,
  }));

  if (folded.length) {
    datasets.push({
      label: `Other (${folded.length})`,
      data: months.map((_, i) => folded.reduce((sum, s) => sum + Number(s.values[i] ?? 0), 0)),
      backgroundColor: palette.rule,
      borderColor: palette.surface,
      borderWidth: 2,
      borderRadius: 3,
      stack: "spend",
      maxBarThickness: 34,
    });
  }

  return (
    <div className="chartjs-card" style={{ height: 300 }}>
      <Bar
        data={{ labels: months.map(monthLabel), datasets }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          scales: {
            x: { stacked: true, grid: { display: false }, ticks: { color: palette.muted } },
            y: {
              stacked: true,
              grid: { color: palette.rule },
              border: { display: false },
              ticks: { color: palette.muted, callback: (v) => moneyShort(Number(v)) },
            },
          },
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: palette.ink, padding: 14 },
            },
            tooltip: {
              // Zero-height segments would otherwise crowd the tooltip with
              // every account that simply had no spend that month.
              filter: (ctx) => Number(ctx.raw) > 0,
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${money(Number(ctx.raw))}`,
              },
            },
          },
        }}
      />
    </div>
  );
}
