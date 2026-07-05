import { CURRENCIES } from "@/lib/format";
import { useFilters, type TimeRange } from "@/store/filters";
import { useRegions } from "@/api/queries";

const RANGES: { value: TimeRange; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_3m", label: "Last 3 mo" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

export function FilterBar() {
  const { region, currency, timeRange, theme, setRegion, setCurrency, setTimeRange, setTheme } =
    useFilters();
  const { data: regions } = useRegions();

  const cycleTheme = () =>
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  const themeIcon = theme === "light" ? "☀" : theme === "dark" ? "☾" : "◑";

  return (
    <div className="filterbar">
      <div className="filterbar__segment" role="group" aria-label="Time range">
        {RANGES.map((r) => (
          <button
            key={r.value}
            className={`seg ${timeRange === r.value ? "seg--on" : ""}`}
            onClick={() => setTimeRange(r.value)}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="filterbar__controls">
        <label className="inline-field">
          <span className="eyebrow">Region</span>
          <select value={region} onChange={(e) => setRegion(e.target.value as never)}>
            <option value="">All</option>
            {regions?.map((r) => (
              <option key={r.region} value={r.region}>
                {r.region}
              </option>
            ))}
          </select>
        </label>

        <label className="inline-field">
          <span className="eyebrow">Currency</span>
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <button className="btn theme-toggle" onClick={cycleTheme} title={`Theme: ${theme}`}>
          <span aria-hidden>{themeIcon}</span>
        </button>
      </div>
    </div>
  );
}
