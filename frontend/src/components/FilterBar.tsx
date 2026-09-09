import { ACCOUNT_TYPE_LABEL } from "@/lib/format";
import { TIME_RANGES, useFilters } from "@/store/filters";
import { useAccounts } from "@/api/queries";

/**
 * Global filters. Currency and region are gone — the app is single-currency
 * (PHP) and single-jurisdiction (PH). Account took their place: with a
 * double-entry chart of accounts, "show me only what touched the GCash wallet"
 * is the slice worth having.
 */
export function FilterBar() {
  const { accountId, timeRange, theme, setAccountId, setTimeRange, setTheme } = useFilters();
  const { data: accounts } = useAccounts();

  const cycleTheme = () =>
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  const themeIcon = theme === "light" ? "☀" : theme === "dark" ? "☾" : "◑";

  // Only balance-sheet accounts make sense as a filter: filtering to an
  // expense account would hide the very entries that fund it.
  const selectable = (accounts ?? []).filter(
    (a) => a.type === "asset" || a.type === "liability",
  );
  const grouped = ["asset", "liability"].map((type) => ({
    type,
    label: ACCOUNT_TYPE_LABEL[type],
    items: selectable.filter((a) => a.type === type),
  }));

  return (
    <div className="filterbar">
      <div className="filterbar__segment" role="group" aria-label="Time range">
        {TIME_RANGES.map((r) => (
          <button
            key={r.value}
            className={`seg ${timeRange === r.value ? "seg--on" : ""}`}
            onClick={() => setTimeRange(r.value)}
            aria-pressed={timeRange === r.value}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="filterbar__controls">
        <label className="inline-field">
          <span className="eyebrow">Account</span>
          <select
            value={accountId ?? ""}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All accounts</option>
            {grouped.map((g) =>
              g.items.length ? (
                <optgroup key={g.type} label={g.label}>
                  {g.items.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </optgroup>
              ) : null,
            )}
          </select>
        </label>

        <button className="btn theme-toggle" onClick={cycleTheme} title={`Theme: ${theme}`}>
          <span aria-hidden>{themeIcon}</span>
        </button>
      </div>
    </div>
  );
}
