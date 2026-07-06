import { Line } from "react-chartjs-2";
import { useChartPalette } from "@/lib/chartColors";

export interface LineSeries {
  label: string;
  data: (number | null)[];
  color: string;
  dashed?: boolean;
  fill?: boolean;
}

export interface TooltipLabelArgs {
  seriesLabel: string;
  value: number;
  previousValue: number | null;
  index: number;
}

/** Generic multi-series line chart (Chart.js) — FX trend, cash flow, expense deltas. */
export function LineChart({
  labels,
  series,
  valueFormatter = (v: number) => String(v),
  height = 240,
  tooltipLabel,
}: {
  labels: string[];
  series: LineSeries[];
  valueFormatter?: (v: number) => string;
  height?: number;
  /** Override the tooltip line's text — e.g. to show a value + its delta vs
   * the previous point. Defaults to `"<series>: <formatted value>"`. */
  tooltipLabel?: (args: TooltipLabelArgs) => string;
}) {
  const palette = useChartPalette();
  if (!labels.length || !series.length) {
    return <div className="empty">Not enough data yet.</div>;
  }

  return (
    <div className="chartjs-card" style={{ height }}>
      <Line
        data={{
          labels,
          datasets: series.map((s) => ({
            label: s.label,
            data: s.data,
            borderColor: s.color,
            backgroundColor: s.fill ? `${s.color}22` : s.color,
            borderDash: s.dashed ? [5, 4] : undefined,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2,
            tension: 0.25,
            fill: !!s.fill,
          })),
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          scales: {
            x: { grid: { display: false }, ticks: { color: palette.muted } },
            y: {
              grid: { color: palette.rule },
              ticks: { color: palette.muted, callback: (v) => valueFormatter(Number(v)) },
            },
          },
          plugins: {
            legend: {
              display: series.length > 1,
              position: "bottom",
              labels: { color: palette.ink },
            },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const value = Number(ctx.raw);
                  if (!tooltipLabel) return `${ctx.dataset.label}: ${valueFormatter(value)}`;
                  const data = series[ctx.datasetIndex]?.data ?? [];
                  const previousValue = ctx.dataIndex > 0 ? data[ctx.dataIndex - 1] : null;
                  return tooltipLabel({
                    seriesLabel: ctx.dataset.label ?? "",
                    value,
                    previousValue: previousValue == null ? null : Number(previousValue),
                    index: ctx.dataIndex,
                  });
                },
              },
            },
          },
        }}
      />
    </div>
  );
}
