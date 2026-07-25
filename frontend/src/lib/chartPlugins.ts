import type { Plugin } from "chart.js";

/**
 * Vertical guide line at the hovered index, synced to Chart.js's own
 * tooltip state so it only appears while a point is actually active — no
 * separate hover-tracking needed. Scoped per-chart via the `plugins` prop
 * (not globally registered) so bar/stacked-bar charts, which don't want a
 * crosshair, are unaffected.
 */
export const crosshairPlugin: Plugin<"line"> = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements();
    if (!active?.length) return;
    const { ctx, chartArea } = chart;
    const x = active[0].element.x;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(128, 128, 128, 0.5)";
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.restore();
  },
};
