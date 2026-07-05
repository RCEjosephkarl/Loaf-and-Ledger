import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Brand } from "@/components/Brand";
import { FilterBar } from "@/components/FilterBar";
import { useFilters } from "@/store/filters";
import "@/components/layout.css";

const NAV = [
  { to: "/", label: "Dashboard", end: true, hint: "01" },
  { to: "/salary", label: "Salary", hint: "02" },
  { to: "/ledger", label: "Ledger", hint: "03" },
  { to: "/budgets", label: "Budgets", hint: "04" },
  { to: "/analytics", label: "Analytics", hint: "05" },
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
            <span className="eyebrow">household accounts</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="nav__link">
              <span className="nav__hint">{n.hint}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__foot eyebrow">v0.0.0 · local</div>
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
