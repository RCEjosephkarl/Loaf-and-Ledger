import {
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";

// BarController + LineController registered together (not just via the
// typed <Bar>/<Line> components) so a single mixed chart — e.g. the
// Analytics monthly combo of income/expense bars + a net-cashflow line —
// can render both dataset types in one canvas.
Chart.register(
  CategoryScale,
  LinearScale,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
  Legend,
);

Chart.defaults.font.family = "'IBM Plex Sans', system-ui, -apple-system, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.boxHeight = 8;
Chart.defaults.plugins.legend.labels.boxWidth = 8;
