import { useNavigate } from "react-router-dom";
import {
  IconClose,
  IconDatabase,
  IconRefresh,
  IconSettings,
  IconSparkles,
} from "@/components/Icons";
import {
  TIME_RANGES,
  useFilters,
  VIEWPORT_PRESETS,
  type Density,
  type FontScale,
  type LedgerPageSize,
  type Theme,
  type TimeRange,
  type ViewportPreset,
} from "@/store/filters";

export function SettingsDrawer() {
  const navigate = useNavigate();
  const {
    settingsDrawerOpen,
    setSettingsDrawerOpen,
    theme,
    setTheme,
    density,
    setDensity,
    viewportPreset,
    setViewportPreset,
    fontScale,
    setFontScale,
    reducedMotion,
    setReducedMotion,
    highContrast,
    setHighContrast,
    defaultPeriod,
    applyDefaultPeriodToAll,
    ledgerPageSize,
    setLedgerPageSize,
    setWelcomeOpen,
    resetPreferences,
  } = useFilters();

  if (!settingsDrawerOpen) return null;

  const goFullSettings = () => {
    setSettingsDrawerOpen(false);
    navigate("/settings");
  };

  return (
    <div
      className="drawer-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) setSettingsDrawerOpen(false);
      }}
    >
      <aside className="settings-drawer">
        <header className="settings-drawer__head">
          <div className="row" style={{ gap: 8 }}>
            <IconSettings size={18} />
            <h3 id="drawer-title">Quick Settings</h3>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            aria-label="Close quick settings"
            onClick={() => setSettingsDrawerOpen(false)}
          >
            <IconClose size={18} />
          </button>
        </header>

        <div className="settings-drawer__body">
          {/* Appearance */}
          <div className="drawer-group">
            <span className="eyebrow">Appearance</span>
            <div className="drawer-field">
              <label>Theme</label>
              <div className="filterbar__segment">
                {(["light", "dark", "system"] as Theme[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`seg ${theme === t ? "seg--on" : ""}`}
                    onClick={() => setTheme(t)}
                  >
                    {t === "light" ? "☀ Light" : t === "dark" ? "☾ Dark" : "◑ Auto"}
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-field">
              <label>UI Density</label>
              <div className="filterbar__segment">
                {(["comfortable", "compact"] as Density[]).map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={`seg ${density === d ? "seg--on" : ""}`}
                    onClick={() => setDensity(d)}
                  >
                    {d === "comfortable" ? "Comfortable" : "Compact"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Viewport Preset */}
          <div className="drawer-group">
            <span className="eyebrow">Window &amp; Viewport Preset</span>
            <div className="drawer-preset-grid">
              {VIEWPORT_PRESETS.map((vp) => (
                <button
                  key={vp.value}
                  type="button"
                  className={`drawer-preset-btn ${
                    viewportPreset === vp.value ? "drawer-preset-btn--active" : ""
                  }`}
                  onClick={() => setViewportPreset(vp.value as ViewportPreset)}
                >
                  <strong>{vp.shortLabel}</strong>
                  <span className="eyebrow fig">{vp.dimensions}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Default Values */}
          <div className="drawer-group">
            <span className="eyebrow">Default Values</span>
            <div className="drawer-field">
              <label>Global Period Scope</label>
              <div className="filterbar__segment">
                {TIME_RANGES.map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    className={`seg ${defaultPeriod === r.value ? "seg--on" : ""}`}
                    onClick={() => applyDefaultPeriodToAll(r.value as TimeRange)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="drawer-field">
              <label>Ledger Page Size</label>
              <div className="filterbar__segment">
                {([10, 20, 50] as LedgerPageSize[]).map((sz) => (
                  <button
                    key={sz}
                    type="button"
                    className={`seg ${ledgerPageSize === sz ? "seg--on" : ""}`}
                    onClick={() => setLedgerPageSize(sz)}
                  >
                    {sz} rows
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Accessibility */}
          <div className="drawer-group">
            <span className="eyebrow">Accessibility</span>
            <div className="drawer-field">
              <label>Font Scale</label>
              <div className="filterbar__segment">
                {(
                  [
                    { value: "sm", label: "Small" },
                    { value: "md", label: "Default" },
                    { value: "lg", label: "Large" },
                  ] as { value: FontScale; label: string }[]
                ).map((s) => (
                  <button
                    key={s.value}
                    type="button"
                    className={`seg ${fontScale === s.value ? "seg--on" : ""}`}
                    onClick={() => setFontScale(s.value)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={highContrast}
                onChange={(e) => setHighContrast(e.target.checked)}
              />
              <span>High contrast borders &amp; ink</span>
            </label>

            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={reducedMotion}
                onChange={(e) => setReducedMotion(e.target.checked)}
              />
              <span>Reduce animations &amp; motion</span>
            </label>
          </div>

          {/* Shortcuts */}
          <div className="drawer-group">
            <span className="eyebrow">Navigation &amp; Maintenance</span>
            <div className="stack" style={{ gap: 8 }}>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setSettingsDrawerOpen(false);
                  setWelcomeOpen(true, "overview");
                }}
              >
                <IconSparkles size={15} />
                <span>Open Welcome Hub &amp; Changelogs</span>
              </button>
              <button
                type="button"
                className="btn"
                onClick={resetPreferences}
              >
                <IconRefresh size={15} />
                <span>Reset UI Preferences</span>
              </button>
            </div>
          </div>
        </div>

        <footer className="settings-drawer__foot">
          <button
            type="button"
            className="btn btn--primary"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={goFullSettings}
          >
            <IconDatabase size={15} />
            <span>All Settings, Database &amp; Data Deletion →</span>
          </button>
        </footer>
      </aside>
    </div>
  );
}
