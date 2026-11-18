import { useLocation } from "react-router-dom";
import {
  IconDesktop,
  IconHistory,
  IconMobile,
  IconResponsive,
  IconSettings,
  IconSparkles,
  IconTablet,
} from "@/components/Icons";
import { useFilters, VIEWPORT_PRESETS, type ViewportPreset } from "@/store/filters";

const ROUTE_TITLES: Record<string, { section: string; title: string }> = {
  "/": { section: "Overview", title: "Dashboard" },
  "/salary": { section: "Planning", title: "Salary & Payroll" },
  "/accounts": { section: "Bookkeeping", title: "Chart of Accounts" },
  "/ledger": { section: "Bookkeeping", title: "Double-Entry Ledger" },
  "/budgets": { section: "Planning", title: "Monthly Budgets" },
  "/analytics": { section: "Overview", title: "Warehouse Analytics" },
  "/settings": { section: "System", title: "Global Settings" },
};

function presetIcon(preset: ViewportPreset) {
  switch (preset) {
    case "desktop":
      return <IconDesktop size={15} />;
    case "tablet":
      return <IconTablet size={15} />;
    case "mobile":
      return <IconMobile size={15} />;
    default:
      return <IconResponsive size={15} />;
  }
}

export function FilterBar() {
  const location = useLocation();
  const {
    theme,
    setTheme,
    viewportPreset,
    setViewportPreset,
    setWelcomeOpen,
    setSettingsDrawerOpen,
  } = useFilters();

  const cycleTheme = () =>
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  const themeIcon = theme === "light" ? "☀" : theme === "dark" ? "☾" : "◑";
  const routeMeta = ROUTE_TITLES[location.pathname] ?? {
    section: "Workspace",
    title: "Loaf & Ledger",
  };

  return (
    <div className="filterbar">
      <div className="topbar__breadcrumb">
        <span className="eyebrow">{routeMeta.section}</span>
        <span className="topbar__sep" aria-hidden="true">
          /
        </span>
        <strong className="topbar__current">{routeMeta.title}</strong>
      </div>

      <div className="topbar__actions">
        {/* Interactive Viewport Size Preset Switcher */}
        <div
          className="filterbar__segment viewport-switcher"
          role="group"
          aria-label="Window viewport preset"
        >
          {VIEWPORT_PRESETS.map((vp) => (
            <button
              key={vp.value}
              type="button"
              className={`seg viewport-switcher__btn ${
                viewportPreset === vp.value ? "seg--on" : ""
              }`}
              aria-pressed={viewportPreset === vp.value}
              title={`${vp.label} (${vp.dimensions})`}
              onClick={() => setViewportPreset(vp.value)}
            >
              {presetIcon(vp.value)}
              <span className="viewport-switcher__label">{vp.shortLabel}</span>
            </button>
          ))}
        </div>

        {/* Welcome & Changelogs Triggers */}
        <button
          type="button"
          className="btn topbar__btn"
          title="Open Welcome Hub"
          onClick={() => setWelcomeOpen(true, "overview")}
        >
          <IconSparkles size={15} />
          <span className="topbar__btn-label">Welcome</span>
        </button>

        <button
          type="button"
          className="btn topbar__btn topbar__btn--changelog"
          title="See Changelogs"
          onClick={() => setWelcomeOpen(true, "changelogs")}
        >
          <IconHistory size={15} />
          <span className="topbar__btn-label">Changelogs</span>
        </button>

        {/* Theme Switcher */}
        <button
          type="button"
          className="btn theme-toggle"
          onClick={cycleTheme}
          title={`Theme: ${theme}`}
          aria-label={`Theme: ${theme}. Change theme`}
        >
          <span aria-hidden>{themeIcon}</span>
        </button>

        {/* Quick Settings Drawer Trigger */}
        <button
          type="button"
          className="btn topbar__btn"
          title="Quick Settings"
          aria-label="Open Quick Settings"
          onClick={() => setSettingsDrawerOpen(true)}
        >
          <IconSettings size={16} />
          <span className="topbar__btn-label">Settings</span>
        </button>
      </div>
    </div>
  );
}
