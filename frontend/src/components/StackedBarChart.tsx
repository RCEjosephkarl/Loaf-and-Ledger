import { Bar } from "react-chartjs-2";
import { useChartPalette } from "@/lib/chartColors";
import { monthLabel, money } from "@/lib/format";
import type { MonthlyCategorySeries } from "@/lib/types";

const PALETTE_KEYS = ["green", "crust", "warn", "good", "debit", "muted"] as const;
const MAX_SLICES = 5;

/** Stacked monthly expense-by-category bar chart. Caps to the top N
 * categories by total spend + an "Other" bucket, cycling the existing theme
 * palette rather than inventing a new categorical color system. */
export function StackedBarChart({
  months,
  series,
  currency,
}: {
  months: string[];
  series: MonthlyCategorySeries[];
  currency: string;
}) {
  const palette = useChartPalette();
  if (!months.length || !series.length) return <div className="empty">No category data yet.</div>;

  const totals = series.map((s) => ({ s, total: s.values.reduce((a, v) => a + Number(v), 0) }));
  totals.sort((a, b) => b.total - a.total);
  const top = totals.slice(0, MAX_SLICES).map((t) => t.s);
  const rest = totals.slice(MAX_SLICES).map((t) => t.s);

  const otherValues = months.map((_, i) => rest.reduce((sum, s) => sum + Number(s.values[i] ?? 0), 0));
  const colors = PALETTE_KEYS.map((k) => palette[k]);

  const datasets = top.map((s, i) => ({
    label: s.category_name,
    data: s.values.map(Number),
    backgroundColor: colors[i % colors.length],
    stack: "expenses",
    borderRadius: 2,
    maxBarThickness: 28,
  }));
  if (rest.length) {
    datasets.push({
      label: "Other",
      data: otherValues,
      backgroundColor: palette.rule,
      stack: "expenses",
      borderRadius: 2,
      maxBarThickness: 28,
    });
  }

  return (
    <div className="chartjs-card">
      <Bar
        data={{ labels: months.map(monthLabel), datasets }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { stacked: true, grid: { display: false }, ticks: { color: palette.muted } },
            y: {
              stacked: true,
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
