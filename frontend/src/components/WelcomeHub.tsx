import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDatabaseOverview, useMeta, useUser } from "@/api/queries";
import { Brand } from "@/components/Brand";
import {
  IconAccounts,
  IconAnalytics,
  IconBudgets,
  IconDashboard,
  IconHistory,
  IconInfo,
  IconLedger,
  IconSalary,
  IconSettings,
  IconSparkles,
} from "@/components/Icons";
import { APP_PILLARS, CHANGELOG_RELEASES, type ChangelogItem } from "@/lib/changelogData";
import { useFilters } from "@/store/filters";

const MODULES = [
  {
    to: "/",
    title: "Dashboard",
    tagline: "Where the dough goes",
    desc: "Balance sheet highlight card, net worth, savings rate, and plain-language insights.",
    icon: IconDashboard,
  },
  {
    to: "/salary",
    title: "Salary",
    tagline: "What survives to net",
    desc: "Philippine TRAIN law calculator, saved salary snapshots, and one-click payslip posting.",
    icon: IconSalary,
  },
  {
    to: "/accounts",
    title: "Accounts",
    tagline: "Every pocket, named",
    desc: "36-account chart of accounts grouped by type with period activity and closing balances.",
    icon: IconAccounts,
  },
  {
    to: "/ledger",
    title: "Ledger",
    tagline: "Dated and dressed",
    desc: "Two-line quick entry and multi-line balanced journal grid with live debit/credit meter.",
    icon: IconLedger,
  },
  {
    to: "/budgets",
    title: "Budgets",
    tagline: "Monthly limits",
    desc: "Expense account limits, utilization bars, and period starting fund carryover.",
    icon: IconBudgets,
  },
  {
    to: "/analytics",
    title: "Analytics",
    tagline: "The four-act narrative",
    desc: "DuckDB OLAP star-schema views: waterfall, ranked spend deltas, burn rate, and runway.",
    icon: IconAnalytics,
  },
];

export function WelcomeHub() {
  const navigate = useNavigate();
  const {
    welcomeOpen,
    welcomeTab,
    setWelcomeOpen,
    showWelcomeOnLaunch,
    setShowWelcomeOnLaunch,
  } = useFilters();
  const { data: meta } = useMeta();
  const { data: user } = useUser();
  const { data: dbInfo } = useDatabaseOverview();
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  if (!welcomeOpen) return null;

  const openModule = (path: string) => {
    setWelcomeOpen(false);
    navigate(path);
  };

  const accountsCount = dbInfo?.tables.find((t) => t.name === "accounts")?.row_count ?? 36;
  const entriesCount = dbInfo?.tables.find((t) => t.name === "journal_entries")?.row_count ?? 0;

  return (
    <div className="welcome-backdrop" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
      <div className="welcome-hub card">
        {/* Top Hero Banner */}
        <header className="welcome-hero">
          <div className="welcome-hero__top">
            <div className="welcome-brand">
              <div className="welcome-brand__mark">
                <Brand size={38} />
              </div>
              <div>
                <div className="welcome-badges">
                  <span className="pill pill--statutory">v0.2.0 · Blue Ink</span>
                  <span className="pill">PHP (₱) · {meta?.modelled_as ?? "PH TRAIN Law"}</span>
                  <span className="pill pill--credit">
                    {dbInfo?.warehouse_ok !== false ? "● OLTP + DuckDB Synced" : "● Warehouse Check"}
                  </span>
                </div>
                <h1 id="welcome-title" className="welcome-title">
                  Welcome to Loaf &amp; Ledger{user?.name ? `, ${user.name}` : ""}
                </h1>
              </div>
            </div>
            <button
              type="button"
              className="btn btn--primary welcome-cta-top"
              onClick={() => setWelcomeOpen(false)}
            >
              Open App →
            </button>
          </div>

          <p className="welcome-lead">
            A personal-finance workbench that keeps a salaried breadwinner&apos;s money in a real{" "}
            <strong>double-entry ledger</strong>, mirrors every posting into a{" "}
            <strong>DuckDB star-schema warehouse</strong>, and tells the story back in plain words.
          </p>

          {/* Primary Action Bar requested by user: Open App, See Changelogs, About the App */}
          <div className="welcome-actions" role="tablist" aria-label="Welcome options">
            <button
              type="button"
              role="tab"
              aria-selected={welcomeTab === "overview"}
              className={`btn ${welcomeTab === "overview" ? "btn--active-tab" : ""}`}
              onClick={() => setWelcomeOpen(true, "overview")}
            >
              <IconSparkles size={16} />
              <span>Workspace Overview</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={welcomeTab === "changelogs"}
              className={`btn ${welcomeTab === "changelogs" ? "btn--active-tab" : ""}`}
              onClick={() => setWelcomeOpen(true, "changelogs")}
            >
              <IconHistory size={16} />
              <span>See Changelogs</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={welcomeTab === "about"}
              className={`btn ${welcomeTab === "about" ? "btn--active-tab" : ""}`}
              onClick={() => setWelcomeOpen(true, "about")}
            >
              <IconInfo size={16} />
              <span>About the App</span>
            </button>
            <button
              type="button"
              className="btn btn--primary welcome-actions__open"
              onClick={() => setWelcomeOpen(false)}
            >
              <span>Open App</span>
            </button>
          </div>
        </header>

        {/* Body Content */}
        <div className="welcome-body">
          {welcomeTab === "overview" && (
            <div className="welcome-section">
              <div className="welcome-stats">
                <div className="welcome-stat">
                  <span className="eyebrow">Active Chart</span>
                  <strong className="fig">{accountsCount} accounts</strong>
                  <span className="muted">Assets, liabilities, equity, P&amp;L</span>
                </div>
                <div className="welcome-stat">
                  <span className="eyebrow">Recorded Journal</span>
                  <strong className="fig">{entriesCount} entries</strong>
                  <span className="muted">Balanced double-entry lines</span>
                </div>
                <div className="welcome-stat">
                  <span className="eyebrow">Tax Regime</span>
                  <strong className="fig">{meta?.tax_year ?? 2025} PH TRAIN</strong>
                  <span className="muted">SSS · PhilHealth · Pag-IBIG · BIR</span>
                </div>
                <div className="welcome-stat">
                  <span className="eyebrow">Storage</span>
                  <strong className="fig">Local First</strong>
                  <span className="muted">SQLite OLTP + DuckDB OLAP</span>
                </div>
              </div>

              <div className="welcome-subhead">
                <h3>Jump straight to a section</h3>
                <span className="eyebrow">Click any module to open the app there</span>
              </div>

              <div className="welcome-grid">
                {MODULES.map((m) => {
                  const Icon = m.icon;
                  return (
                    <button
                      key={m.to}
                      type="button"
                      className="welcome-card"
                      onClick={() => openModule(m.to)}
                    >
                      <div className="welcome-card__head">
                        <span className="welcome-card__icon">
                          <Icon size={20} />
                        </span>
                        <div>
                          <div className="welcome-card__title">{m.title}</div>
                          <div className="eyebrow">{m.tagline}</div>
                        </div>
                      </div>
                      <p className="welcome-card__desc">{m.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {welcomeTab === "changelogs" && (
            <div className="welcome-section">
              <div className="welcome-subhead">
                <div>
                  <h3>Release History &amp; Changelogs</h3>
                  <span className="eyebrow">
                    Tracked in Keep a Changelog &amp; Semantic Versioning format
                  </span>
                </div>
                <div className="filterbar__segment" role="group" aria-label="Filter changelog">
                  {(["all", "Added", "Changed", "Fixed"] as const).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      className={`seg ${categoryFilter === cat ? "seg--on" : ""}`}
                      onClick={() => setCategoryFilter(cat)}
                    >
                      {cat === "all" ? "All changes" : cat}
                    </button>
                  ))}
                </div>
              </div>

              <div className="changelog-timeline">
                {CHANGELOG_RELEASES.map((rel) => {
                  const filtered =
                    categoryFilter === "all"
                      ? rel.items
                      : rel.items.filter((i) => i.category === categoryFilter);
                  if (!filtered.length) return null;
                  return (
                    <article key={rel.version} className="changelog-release">
                      <div className="changelog-release__head">
                        <div className="row" style={{ gap: 10 }}>
                          <h4 className="fig changelog-release__ver">{rel.version}</h4>
                          {rel.badge && <span className="pill pill--statutory">{rel.badge}</span>}
                        </div>
                        <span className="eyebrow fig">{rel.date}</span>
                      </div>
                      <p className="changelog-release__summary">{rel.summary}</p>
                      <ul className="changelog-items">
                        {filtered.map((item: ChangelogItem, idx: number) => (
                          <li key={idx} className="changelog-item">
                            <span
                              className={`pill pill--sm ${
                                item.category === "Added"
                                  ? "pill--credit"
                                  : item.category === "Fixed"
                                    ? "pill--statutory"
                                    : ""
                              }`}
                            >
                              {item.category}
                            </span>
                            <div>
                              <strong>{item.title}:</strong>{" "}
                              <span className="muted">{item.detail}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </article>
                  );
                })}
              </div>
            </div>
          )}

          {welcomeTab === "about" && (
            <div className="welcome-section">
              <div className="welcome-subhead">
                <div>
                  <h3>About Loaf &amp; Ledger</h3>
                  <span className="eyebrow">
                    Why personal finance deserves a real double-entry journal and an analytical warehouse
                  </span>
                </div>
              </div>

              <div className="about-pillars">
                {APP_PILLARS.map((p) => (
                  <div key={p.numeral} className="about-pillar">
                    <span className="about-pillar__num fig">{p.numeral}</span>
                    <div>
                      <h4>{p.title}</h4>
                      <p className="muted">{p.description}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="about-arch card">
                <div className="card__head">
                  <h4>Two Databases on Purpose: Write-Through ETL Architecture</h4>
                  <span className="pill">Zero Refresh Lag</span>
                </div>
                <div className="card__body about-arch__flow">
                  <div className="arch-node">
                    <span className="eyebrow">1. Write Side (OLTP)</span>
                    <strong>SQLite / PostgreSQL Journal</strong>
                    <p className="muted">
                      Normalized system of record. Enforces <code>SUM(debit) = SUM(credit)</code> on
                      every entry across 36 PH accounts.
                    </p>
                  </div>
                  <div className="arch-arrow" aria-hidden="true">
                    →
                  </div>
                  <div className="arch-node">
                    <span className="eyebrow">2. Synchronous Bridge</span>
                    <strong>Write-Through ETL</strong>
                    <p className="muted">
                      Loads journal lines and refreshes monthly &amp; daily rollups inside the same
                      request lifecycle.
                    </p>
                  </div>
                  <div className="arch-arrow" aria-hidden="true">
                    →
                  </div>
                  <div className="arch-node">
                    <span className="eyebrow">3. Read Side (OLAP)</span>
                    <strong>DuckDB Star Schema</strong>
                    <p className="muted">
                      Columnar facts (<code>fact_ledger_line</code>, <code>fact_payslip_item</code>)
                      and dimensions powering instant analytics.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="welcome-foot">
          <label className="welcome-check">
            <input
              type="checkbox"
              checked={showWelcomeOnLaunch}
              onChange={(e) => setShowWelcomeOnLaunch(e.target.checked)}
            />
            <span>Show this welcome page when launching the app</span>
          </label>

          <div className="row" style={{ gap: 10 }}>
            <button
              type="button"
              className="btn"
              onClick={() => openModule("/settings")}
            >
              <IconSettings size={15} />
              <span>Global Settings</span>
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setWelcomeOpen(false)}
            >
              Open App
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
