import { Bar } from "react-chartjs-2";
import { useChartPalette } from "@/lib/chartColors";
import { money, moneyShort } from "@/lib/format";

export interface WaterfallStep {
  label: string;
  /** Positive grows the running total, negative shrinks it. */
  delta: number;
  /** A total/subtotal bar drawn from zero rather than floating. */
  isTotal?: boolean;
}

/**
 * Gross-to-net waterfall.
 *
 * Chart.js has no waterfall type; this builds one from floating bars — each
 * datum is a `[from, to]` pair, so a deduction hangs from where the previous
 * bar ended. That is the whole point of the form: you can see each withholding
 * take its bite out of gross, rather than reading five numbers and doing the
 * subtraction yourself.
 *
 * Color here encodes polarity (start/end totals, versus amounts taken away),
 * not identity, so it uses the reserved semantic roles rather than categorical
 * slots — and the sign is also carried by the bar's direction and its label,
 * never by color alone.
 */
export function WaterfallChart({
  steps,
  height = 340,
}: {
  steps: WaterfallStep[];
  height?: number;
}) {
  const palette = useChartPalette();
  if (!steps.length) return <div className="empty">No payslip to break down yet.</div>;

  let running = 0;
  const bars = steps.map((step) => {
    if (step.isTotal) {
      running = step.delta;
      return { ...step, range: [0, step.delta] as [number, number], value: step.delta };
    }
    const from = running;
    running += step.delta;
    return { ...step, range: [from, running] as [number, number], value: step.delta };
  });

  return (
    <div className="chartjs-card" style={{ height }}>
      <Bar
        data={{
          labels: bars.map((b) => b.label),
          datasets: [
            {
              label: "Amount",
              data: bars.map((b) => b.range),
              backgroundColor: bars.map((b) =>
                b.isTotal ? palette.credit : b.value < 0 ? palette.debit : palette.green,
              ),
              borderRadius: 4,
              borderSkipped: false,
              // A 2px surface ring keeps a thin deduction bar from melting
              // into the gridline it floats on.
              borderColor: palette.surface,
              borderWidth: 2,
              maxBarThickness: 56,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                color: palette.muted,
                autoSkip: false,
                // Deduction labels are long and the bars are narrow; left flat
                // they overlap into an unreadable run of words.
                maxRotation: 45,
                minRotation: 45,
              },
            },
            y: {
              grid: { color: palette.rule },
              border: { display: false },
              beginAtZero: true,
              ticks: { color: palette.muted, callback: (v) => moneyShort(Number(v)) },
            },
          },
          plugins: {
            // One series; the title names it, so a legend box would be noise.
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const bar = bars[ctx.dataIndex];
                  if (bar.isTotal) return money(bar.value);
                  const sign = bar.value < 0 ? "−" : "+";
                  return `${sign}${money(Math.abs(bar.value))}  →  ${money(bar.range[1])}`;
                },
              },
            },
          },
        }}
      />
    </div>
  );
}
