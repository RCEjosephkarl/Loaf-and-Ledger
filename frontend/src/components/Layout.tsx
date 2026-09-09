import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Brand } from "@/components/Brand";
import { FilterBar } from "@/components/FilterBar";
import { useFilters } from "@/store/filters";
import "@/components/layout.css";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/salary", label: "Salary" },
  { to: "/accounts", label: "Accounts" },
  { to: "/ledger", label: "Ledger" },
  { to: "/budgets", label: "Budgets" },
  { to: "/analytics", label: "Analytics" },
];

function useTheme() {
  const theme = useFilters((s) => s.theme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme]);
}

export function Layout() {
  useTheme();
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <Brand />
          <div className="stack">
            <span className="sidebar__name">Loaf &amp; Ledger</span>
            <span className="eyebrow">Household accounts</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="nav__link">
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__foot eyebrow">
          Version 0.1.0. Philippine peso, stored on this device.
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
    </div>
  );
}
