import { Bar } from "react-chartjs-2";
import { useChartPalette } from "@/lib/chartColors";
import { money, percent } from "@/lib/format";
import type { SalaryProfile } from "@/lib/types";

/**
 * Horizontal bar of effective tax-and-contribution rate, one bar per saved
 * salary profile. Rate is the one figure that's fair to compare across
 * regions — gross/net stay in each profile's own currency, so those are
 * relegated to the tooltip rather than the axis. Hover state is lifted so
 * the profiles table can highlight the matching row (and vice versa).
 */
export function ProfileCompareChart({
  profiles,
  hoveredId,
  onHoverChange,
}: {
  profiles: SalaryProfile[];
  hoveredId: number | null;
  onHoverChange: (id: number | null) => void;
}) {
  const palette = useChartPalette();
  if (profiles.length < 2) return null;

  const active = profiles.find((p) => p.is_active) ?? null;
  const rates = profiles.map((p) => Number(p.breakdown.effective_rate) * 100);
  const colors = profiles.map((p) => {
    if (p.id === hoveredId) return palette.debit;
    if (p.is_active) return palette.crust;
    return palette.green;
  });

  return (
    <div className="chartjs-card" style={{ height: Math.max(56 * profiles.length, 130) }}>
      <Bar
        data={{
          labels: profiles.map((p) => `${p.label} · ${p.region}`),
          datasets: [
            {
              label: "Effective rate",
              data: rates,
              backgroundColor: colors,
              borderRadius: 4,
              maxBarThickness: 26,
            },
          ],
        }}
        options={{
          indexAxis: "y" as const,
          responsive: true,
          maintainAspectRatio: false,
          onHover: (_evt, elements) => {
            onHoverChange(elements.length ? profiles[elements[0].index].id : null);
          },
          scales: {
            x: {
              grid: { color: palette.rule },
              ticks: { color: palette.muted, callback: (v) => `${v}%` },
            },
            y: { grid: { display: false }, ticks: { color: palette.ink } },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const p = profiles[ctx.dataIndex];
                  const lines = [`Effective rate: ${percent(p.breakdown.effective_rate, 1)}`];
                  if (active && p.id !== active.id) {
                    const deltaPts =
                      Number(p.breakdown.effective_rate) * 100 - Number(active.breakdown.effective_rate) * 100;
                    const sign = deltaPts >= 0 ? "+" : "";
                    lines.push(`${sign}${deltaPts.toFixed(1)} pts vs active (${active.label})`);
                  }
                  lines.push(`Net take-home: ${money(p.net_amount, p.currency)} / yr`);
                  return lines;
                },
              },
            },
          },
        }}
      />
    </div>
  );
}
