import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useWarehouseStatus } from "@/api/queries";
import { Brand } from "@/components/Brand";
import { FilterBar } from "@/components/FilterBar";
import {
  IconAccounts,
  IconAnalytics,
  IconBudgets,
  IconChevronLeft,
  IconChevronRight,
  IconDashboard,
  IconLedger,
  IconSalary,
  IconSettings,
  IconSparkles,
} from "@/components/Icons";
import { SettingsDrawer } from "@/components/SettingsDrawer";
import { WelcomeHub } from "@/components/WelcomeHub";
import { useFilters, VIEWPORT_PRESETS } from "@/store/filters";
import "@/components/layout.css";

const NAV_GROUPS = [
  {
    group: "Overview",
    items: [
      { to: "/", label: "Dashboard", end: true, icon: IconDashboard },
      { to: "/analytics", label: "Analytics", icon: IconAnalytics },
    ],
  },
  {
    group: "Bookkeeping",
    items: [
      { to: "/ledger", label: "Ledger", icon: IconLedger },
      { to: "/accounts", label: "Accounts", icon: IconAccounts },
    ],
  },
  {
    group: "Planning",
    items: [
      { to: "/salary", label: "Salary", icon: IconSalary },
      { to: "/budgets", label: "Budgets", icon: IconBudgets },
    ],
  },
  {
    group: "System",
    items: [{ to: "/settings", label: "Settings", icon: IconSettings }],
  },
];

const MOBILE_NAV = [
  { to: "/", label: "Dashboard", end: true, icon: IconDashboard },
  { to: "/ledger", label: "Ledger", icon: IconLedger },
  { to: "/accounts", label: "Accounts", icon: IconAccounts },
  { to: "/salary", label: "Salary", icon: IconSalary },
  { to: "/budgets", label: "Budgets", icon: IconBudgets },
  { to: "/analytics", label: "Analytics", icon: IconAnalytics },
  { to: "/settings", label: "Settings", icon: IconSettings },
];

function useRootPreferences() {
  const theme = useFilters((s) => s.theme);
  const density = useFilters((s) => s.density);
  const fontScale = useFilters((s) => s.fontScale);
  const reducedMotion = useFilters((s) => s.reducedMotion);
  const highContrast = useFilters((s) => s.highContrast);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);

    root.setAttribute("data-density", density);
    root.setAttribute("data-font-scale", fontScale);
    root.setAttribute("data-reduce-motion", reducedMotion ? "true" : "false");
    root.setAttribute("data-contrast", highContrast ? "high" : "normal");
  }, [theme, density, fontScale, reducedMotion, highContrast]);
}

export function Layout() {
  useRootPreferences();
  const {
    sidebarCollapsed,
    toggleSidebar,
    viewportPreset,
    setViewportPreset,
    setWelcomeOpen,
  } = useFilters();
  const { data: whStatus } = useWarehouseStatus();

  const activePresetMeta = VIEWPORT_PRESETS.find((v) => v.value === viewportPreset);
  const isPresetFramed = viewportPreset !== "responsive";

  return (
    <div className={`viewport-stage ${isPresetFramed ? "viewport-stage--framed" : ""}`}>
      {isPresetFramed && activePresetMeta && (
        <div className="viewport-banner" role="region" aria-label="Active viewport preset">
          <span>
            Viewport Preset: <strong>{activePresetMeta.label}</strong> ({activePresetMeta.dimensions})
          </span>
          <button
            type="button"
            className="btn btn--sm"
            onClick={() => setViewportPreset("responsive")}
          >
            Reset to Fluid Window
          </button>
        </div>
      )}

      <div
        className={`app app--preset-${viewportPreset} ${
          sidebarCollapsed ? "app--rail-collapsed" : ""
        }`}
      >
        <aside className={`sidebar ${sidebarCollapsed ? "sidebar--collapsed" : ""}`}>
          <div className="sidebar__top">
            <button
              type="button"
              className="sidebar__brand"
              title="Open Welcome Hub"
              onClick={() => setWelcomeOpen(true, "overview")}
            >
              <div className="sidebar__emblem">
                <Brand size={26} />
              </div>
              {!sidebarCollapsed && (
                <div className="stack sidebar__brand-text">
                  <span className="sidebar__name">Loaf &amp; Ledger</span>
                  <span className="eyebrow">Double-entry books</span>
                </div>
              )}
            </button>

            <button
              type="button"
              className="rail-toggle"
              onClick={toggleSidebar}
              aria-label={sidebarCollapsed ? "Expand navigation rail" : "Collapse navigation rail"}
              title={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
            >
              {sidebarCollapsed ? <IconChevronRight size={16} /> : <IconChevronLeft size={16} />}
            </button>
          </div>

          <nav className="nav" aria-label="Main navigation">
            {NAV_GROUPS.map((group) => (
              <div key={group.group} className="nav__group">
                {!sidebarCollapsed && <span className="nav__group-label">{group.group}</span>}
                {group.items.map((n) => {
                  const Icon = n.icon;
                  return (
                    <NavLink
                      key={n.to}
                      to={n.to}
                      end={n.end}
                      title={sidebarCollapsed ? n.label : undefined}
                      className="nav__link"
                    >
                      <span className="nav__icon">
                        <Icon size={18} />
                      </span>
                      {!sidebarCollapsed && <span className="nav__label">{n.label}</span>}
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar__foot">
            <button
              type="button"
              className="rail-welcome-btn"
              title="Welcome Hub, Changelogs & About"
              onClick={() => setWelcomeOpen(true, "overview")}
            >
              <IconSparkles size={16} />
              {!sidebarCollapsed && <span>Welcome &amp; Tour</span>}
            </button>

            <div
              className="rail-status"
              title={
                whStatus?.ok !== false
                  ? "OLTP & DuckDB OLAP warehouse synchronized"
                  : "Warehouse has uncommitted drift"
              }
            >
              <span
                className={`rail-status__dot ${
                  whStatus?.ok === false ? "rail-status__dot--warn" : "rail-status__dot--ok"
                }`}
              />
              {!sidebarCollapsed && (
                <span className="eyebrow">
                  {whStatus?.ok === false ? "Warehouse drift" : "v0.2.0 · PHP (₱)"}
                </span>
              )}
            </div>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <FilterBar />
          </header>
          <main className="content">
            <Outlet />
          </main>
        </div>

        {/* Mobile Bottom Navigation Bar */}
        <nav className="mobile-nav" aria-label="Mobile navigation">
          {MOBILE_NAV.map((n) => {
            const Icon = n.icon;
            return (
              <NavLink key={n.to} to={n.to} end={n.end} className="mobile-nav__link">
                <Icon size={18} />
                <span>{n.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      <WelcomeHub />
      <SettingsDrawer />
    </div>
  );
}
