import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  useDatabaseOverview,
  useDeleteData,
  useRebuildWarehouse,
  useResetBaseline,
  useSeedDemo,
  useTablePreview,
  useUpdateUser,
  useUser,
} from "@/api/queries";
import {
  IconDatabase,
  IconDownload,
  IconRefresh,
  IconSettings,
  IconSparkles,
  IconTrash,
} from "@/components/Icons";
import { InfoNote } from "@/components/InfoNote";
import { exportLedgerUrl, exportTrialBalanceUrl } from "@/lib/api";
import type { DataDeletionTarget, EntryKind, PayPeriod } from "@/lib/types";
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

type SettingsSection =
  | "appearance"
  | "defaults"
  | "accessibility"
  | "database"
  | "reset"
  | "deletion";

const SECTIONS: { id: SettingsSection; label: string; badge?: string; desc: string }[] = [
  {
    id: "appearance",
    label: "Appearance",
    desc: "Theme, UI density, navigation rail, and viewport size presets.",
  },
  {
    id: "defaults",
    label: "Default values",
    desc: "Household profile, default period scope, payroll period, and ledger defaults.",
  },
  {
    id: "accessibility",
    label: "Accessibility",
    desc: "Typography scale, reduced motion, high contrast, and CVD-safe palette.",
  },
  {
    id: "database",
    label: "Database navigation",
    badge: "OLTP + OLAP",
    desc: "Inspect SQLite & DuckDB tables, preview rows, rebuild warehouse, or export CSVs.",
  },
  {
    id: "reset",
    label: "Reset",
    desc: "Restore UI preferences or reset the ledger to the clean 36-account baseline.",
  },
  {
    id: "deletion",
    label: "Data deletion",
    badge: "Danger",
    desc: "Granular or complete removal of entries, budgets, salary profiles, and custom accounts.",
  },
];

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function Settings() {
  const [activeSection, setActiveSection] = useState<SettingsSection>("appearance");
  const [selectedTable, setSelectedTable] = useState<string>("accounts");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [banner, setBanner] = useState<{ tone: "good" | "warn"; text: string } | null>(null);

  const {
    theme,
    setTheme,
    density,
    setDensity,
    sidebarCollapsed,
    setSidebarCollapsed,
    viewportPreset,
    setViewportPreset,
    showWelcomeOnLaunch,
    setShowWelcomeOnLaunch,
    defaultPeriod,
    setDefaultPeriod,
    applyDefaultPeriodToAll,
    defaultPayPeriod,
    setDefaultPayPeriod,
    defaultEntryKind,
    setDefaultEntryKind,
    ledgerPageSize,
    setLedgerPageSize,
    fontScale,
    setFontScale,
    reducedMotion,
    setReducedMotion,
    highContrast,
    setHighContrast,
    setWelcomeOpen,
    resetPreferences,
  } = useFilters();

  const { data: user } = useUser();
  const updateUser = useUpdateUser();
  const [userName, setUserName] = useState("");
  const [userEmail, setUserEmail] = useState("");

  useEffect(() => {
    if (user) {
      setUserName(user.name ?? "");
      setUserEmail(user.email ?? "");
    }
  }, [user]);

  const { data: dbInfo, isLoading: dbLoading, refetch: refetchDb } = useDatabaseOverview();
  const { data: preview, isLoading: previewLoading } = useTablePreview(
    activeSection === "database" ? selectedTable : null,
    15,
  );
  const rebuildWarehouse = useRebuildWarehouse();
  const resetBaseline = useResetBaseline();
  const seedDemo = useSeedDemo();
  const deleteData = useDeleteData();

  const showNotice = (text: string, tone: "good" | "warn" = "good") => {
    setBanner({ tone, text });
  };

  const handleSaveUser = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateUser.mutateAsync({
      name: userName.trim() || "Breadwinner",
      email: userEmail.trim() || null,
    });
    showNotice("Saved household profile details.");
  };

  const handleResetBaseline = async () => {
    if (
      !confirm(
        "Reset the database to the clean 36-account zero-balance baseline? A timestamped SQLite backup will be created automatically before resetting.",
      )
    ) {
      return;
    }
    const res = await resetBaseline.mutateAsync();
    showNotice(
      `${res.detail}${res.backup_file ? ` Backup saved as ${res.backup_file}.` : ""}`,
      "good",
    );
  };

  const handleSeedDemo = async () => {
    const res = await seedDemo.mutateAsync();
    showNotice(
      `${res.detail} (${res.counts.journal_entries ?? 0} entries, ${res.warehouse_counts.fact_ledger_line ?? 0} warehouse lines).`,
      "good",
    );
  };

  const handleDeleteTarget = async (target: DataDeletionTarget, label: string) => {
    if (
      !confirm(
        `Are you sure you want to delete ${label}? A SQLite backup will be created before removal.`,
      )
    ) {
      return;
    }
    const res = await deleteData.mutateAsync(target);
    if (target === "all_financial") setDeleteConfirmText("");
    showNotice(
      `${res.detail}${res.backup_file ? ` Backup: ${res.backup_file}.` : ""}`,
      "warn",
    );
  };

  return (
    <div className="settings-page">
      <div className="page-head">
        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <h1>
            Global Settings
            <InfoNote label="About global settings" lead="Tailor the workbench & inspect the books.">
              <p>
                Configure appearance, viewport presets, default values, accessibility, and inspect or
                maintain both databases (the SQLite OLTP journal and the DuckDB OLAP warehouse).
              </p>
            </InfoNote>
          </h1>
          <div className="row" style={{ gap: 8 }}>
            <button
              type="button"
              className="btn"
              onClick={() => setWelcomeOpen(true, "overview")}
            >
              <IconSparkles size={15} />
              <span>Open Welcome Hub</span>
            </button>
          </div>
        </div>
      </div>

      {banner && (
        <div className={`callout callout--${banner.tone}`} role="status">
          <span>{banner.text}</span>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => setBanner(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="settings-layout">
        {/* Left Sub-navigation */}
        <nav className="settings-nav card" aria-label="Settings categories">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`settings-nav__item ${
                activeSection === s.id ? "settings-nav__item--active" : ""
              }`}
              onClick={() => setActiveSection(s.id)}
            >
              <div className="settings-nav__top">
                <span>{s.label}</span>
                {s.badge && (
                  <span
                    className={`pill pill--sm ${
                      s.id === "deletion" ? "pill--debit" : "pill--statutory"
                    }`}
                  >
                    {s.badge}
                  </span>
                )}
              </div>
              <span className="eyebrow settings-nav__desc">{s.desc}</span>
            </button>
          ))}
        </nav>

        {/* Right Active Panel */}
        <div className="settings-content">
          {/* ==================== 1. APPEARANCE ==================== */}
          {activeSection === "appearance" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="card">
                <div className="card__head">
                  <h3>Theme &amp; Surface</h3>
                  <span className="pill">Blue Ink Palette</span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Color theme</strong>
                      <p className="muted settings-row__sub">
                        Cool paper by day, night ink after dark, or follow your operating system.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Color theme">
                      {(["light", "dark", "system"] as Theme[]).map((t) => (
                        <button
                          key={t}
                          type="button"
                          className={`seg ${theme === t ? "seg--on" : ""}`}
                          aria-pressed={theme === t}
                          onClick={() => setTheme(t)}
                        >
                          {t === "light" ? "☀ Light" : t === "dark" ? "☾ Dark" : "◑ System"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Interface density</strong>
                      <p className="muted settings-row__sub">
                        Adjust table row spacing, card padding, and grid gaps across all pages.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Interface density">
                      {(["comfortable", "compact"] as Density[]).map((d) => (
                        <button
                          key={d}
                          type="button"
                          className={`seg ${density === d ? "seg--on" : ""}`}
                          aria-pressed={density === d}
                          onClick={() => setDensity(d)}
                        >
                          {d === "comfortable" ? "Comfortable" : "Compact"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Navigation rail mode</strong>
                      <p className="muted settings-row__sub">
                        Expand the left rail to show labels and groups, or collapse to a slim icon rail.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Navigation rail mode">
                      <button
                        type="button"
                        className={`seg ${!sidebarCollapsed ? "seg--on" : ""}`}
                        onClick={() => setSidebarCollapsed(false)}
                      >
                        Expanded
                      </button>
                      <button
                        type="button"
                        className={`seg ${sidebarCollapsed ? "seg--on" : ""}`}
                        onClick={() => setSidebarCollapsed(true)}
                      >
                        Collapsed rail
                      </button>
                    </div>
                  </div>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Window Size &amp; Viewport Preset</h3>
                  <span className="eyebrow">Container-aware responsive layout</span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Preset window size</strong>
                      <p className="muted settings-row__sub">
                        Lock the app shell to Desktop, Tablet (Landscape), or Mobile dimensions — or
                        keep Responsive (Auto) to adapt fluidly as you resize the window.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Viewport preset">
                      {VIEWPORT_PRESETS.map((vp) => (
                        <button
                          key={vp.value}
                          type="button"
                          className={`seg ${viewportPreset === vp.value ? "seg--on" : ""}`}
                          aria-pressed={viewportPreset === vp.value}
                          onClick={() => setViewportPreset(vp.value as ViewportPreset)}
                        >
                          {vp.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Welcome page on launch</strong>
                      <p className="muted settings-row__sub">
                        Display the Welcome Hub (with Changelogs, About, and Open App options) when
                        opening the application.
                      </p>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={showWelcomeOnLaunch}
                        onChange={(e) => setShowWelcomeOnLaunch(e.target.checked)}
                      />
                      <span>{showWelcomeOnLaunch ? "Shown on launch" : "Hidden on launch"}</span>
                    </label>
                  </div>
                </div>
              </section>
            </div>
          )}

          {/* ==================== 2. DEFAULT VALUES ==================== */}
          {activeSection === "defaults" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="card">
                <div className="card__head">
                  <h3>Household Profile</h3>
                  <span className="pill">Single-user instance</span>
                </div>
                <div className="card__body">
                  <form className="form-row" onSubmit={handleSaveUser}>
                    <label className="field field--wide">
                      <span className="eyebrow">Display name</span>
                      <input
                        value={userName}
                        onChange={(e) => setUserName(e.target.value)}
                        placeholder="Breadwinner"
                      />
                    </label>
                    <label className="field field--wide">
                      <span className="eyebrow">Email (optional)</span>
                      <input
                        type="email"
                        value={userEmail}
                        onChange={(e) => setUserEmail(e.target.value)}
                        placeholder="you@example.com"
                      />
                    </label>
                    <button
                      type="submit"
                      className="btn btn--primary"
                      disabled={updateUser.isPending}
                    >
                      {updateUser.isPending ? "Saving…" : "Save profile"}
                    </button>
                  </form>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Section &amp; Form Defaults</h3>
                  <span className="eyebrow">Pre-filled values across modules</span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Default time period scope</strong>
                      <p className="muted settings-row__sub">
                        Preferred date range for Dashboard, Accounts, and Analytics.
                      </p>
                    </div>
                    <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                      <select
                        value={defaultPeriod}
                        onChange={(e) => setDefaultPeriod(e.target.value as TimeRange)}
                      >
                        {TIME_RANGES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => {
                          applyDefaultPeriodToAll(defaultPeriod);
                          showNotice("Applied default period to Dashboard, Accounts, and Analytics.");
                        }}
                      >
                        Apply to all sections now
                      </button>
                    </div>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Default salary pay period</strong>
                      <p className="muted settings-row__sub">
                        Initial pay frequency selected on the Salary calculator when no profile is
                        loaded.
                      </p>
                    </div>
                    <select
                      value={defaultPayPeriod}
                      onChange={(e) => setDefaultPayPeriod(e.target.value as PayPeriod)}
                    >
                      <option value="monthly">Monthly (12/yr)</option>
                      <option value="fortnightly">Fortnightly (26/yr)</option>
                      <option value="annual">Annual (1/yr)</option>
                    </select>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Default ledger quick-entry kind</strong>
                      <p className="muted settings-row__sub">
                        Starting tab on the Ledger &ldquo;Record an entry&rdquo; form.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Default entry kind">
                      {(
                        [
                          { value: "expense", label: "Money out" },
                          { value: "income", label: "Money in" },
                          { value: "transfer", label: "Transfer" },
                        ] as { value: EntryKind; label: string }[]
                      ).map((k) => (
                        <button
                          key={k.value}
                          type="button"
                          className={`seg ${defaultEntryKind === k.value ? "seg--on" : ""}`}
                          onClick={() => setDefaultEntryKind(k.value)}
                        >
                          {k.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Ledger rows per page</strong>
                      <p className="muted settings-row__sub">
                        Number of journal entries shown per page on the Ledger screen.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Ledger page size">
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
              </section>
            </div>
          )}

          {/* ==================== 3. ACCESSIBILITY ==================== */}
          {activeSection === "accessibility" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="card">
                <div className="card__head">
                  <h3>Visual &amp; Motion Accessibility</h3>
                  <span className="pill">WCAG &amp; CVD Tuned</span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Text &amp; figure size scale</strong>
                      <p className="muted settings-row__sub">
                        Scale body copy, headings, and monospaced ledger figures across the app.
                      </p>
                    </div>
                    <div className="filterbar__segment" role="group" aria-label="Font size scale">
                      {(
                        [
                          { value: "sm", label: "Small (93%)" },
                          { value: "md", label: "Default (100%)" },
                          { value: "lg", label: "Large (110%)" },
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

                  <div className="settings-row">
                    <div>
                      <strong>High contrast borders &amp; ink</strong>
                      <p className="muted settings-row__sub">
                        Strengthens card rules, table grid lines, focus rings, and secondary text
                        contrast.
                      </p>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={highContrast}
                        onChange={(e) => setHighContrast(e.target.checked)}
                      />
                      <span>{highContrast ? "High contrast on" : "Standard contrast"}</span>
                    </label>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Reduced motion</strong>
                      <p className="muted settings-row__sub">
                        Disable transitions, smooth animations, and hover motion effects.
                      </p>
                    </div>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={reducedMotion}
                        onChange={(e) => setReducedMotion(e.target.checked)}
                      />
                      <span>{reducedMotion ? "Motion reduced" : "Standard motion"}</span>
                    </label>
                  </div>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Colour-Vision Deficiency (CVD) &amp; Tabular Figures</h3>
                </div>
                <div className="card__body">
                  <p className="muted" style={{ marginTop: 0 }}>
                    Loaf &amp; Ledger uses a fixed 8-slot categorical chart palette validated under
                    deuteranopia, protanopia, and tritanopia simulations on both light and dark
                    surfaces. All monetary figures use <code>font-variant-numeric: tabular-nums</code>{" "}
                    in <strong>DM Mono</strong> so decimal columns always align vertically.
                  </p>
                </div>
              </section>
            </div>
          )}

          {/* ==================== 4. DATABASE NAVIGATION ==================== */}
          {activeSection === "database" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="stat-grid">
                <div className="card stat">
                  <span className="eyebrow">OLTP System of Record</span>
                  <div className="stat__value fig" style={{ fontSize: 22 }}>
                    {dbInfo?.oltp_engine?.toUpperCase() ?? "SQLITE"}
                  </div>
                  <span className="stat__sub muted">
                    Size: {formatBytes(dbInfo?.oltp_size_bytes)} · Backups:{" "}
                    {dbInfo?.backups_count ?? 0}
                  </span>
                </div>
                <div className="card stat">
                  <span className="eyebrow">OLAP DuckDB Warehouse</span>
                  <div className="stat__value fig" style={{ fontSize: 22 }}>
                    {dbInfo?.warehouse_ok ? "Synced" : "Stale / Drift"}
                  </div>
                  <span className="stat__sub muted">
                    Size: {formatBytes(dbInfo?.olap_size_bytes)} · Drift:{" "}
                    {dbInfo?.warehouse_drift ?? 0} lines
                  </span>
                </div>
                <div className="card stat">
                  <span className="eyebrow">Warehouse Operations</span>
                  <div className="row" style={{ gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={rebuildWarehouse.isPending}
                      onClick={async () => {
                        await rebuildWarehouse.mutateAsync();
                        refetchDb();
                        showNotice("Rebuilt DuckDB star-schema warehouse from OLTP journal.");
                      }}
                    >
                      <IconRefresh size={15} />
                      <span>
                        {rebuildWarehouse.isPending ? "Rebuilding…" : "Rebuild Warehouse"}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="btn"
                      disabled={seedDemo.isPending}
                      onClick={handleSeedDemo}
                    >
                      <IconDatabase size={15} />
                      <span>{seedDemo.isPending ? "Seeding…" : "Seed Demo Data"}</span>
                    </button>
                  </div>
                  <span className="stat__sub muted">In-process ETL reload without downtime</span>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Quick Navigation &amp; CSV Exports</h3>
                  <span className="eyebrow">Jump to domain views or stream verified CSVs</span>
                </div>
                <div className="card__body">
                  <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                    <Link className="btn" to="/accounts">
                      Chart of Accounts →
                    </Link>
                    <Link className="btn" to="/ledger">
                      Journal Entries →
                    </Link>
                    <Link className="btn" to="/salary">
                      Salary Profiles →
                    </Link>
                    <Link className="btn" to="/budgets">
                      Monthly Budgets →
                    </Link>
                    <Link className="btn" to="/analytics">
                      Warehouse Analytics →
                    </Link>
                    <a className="btn" href={exportLedgerUrl()}>
                      <IconDownload size={15} />
                      <span>Export Ledger CSV</span>
                    </a>
                    <a className="btn" href={exportTrialBalanceUrl()}>
                      <IconDownload size={15} />
                      <span>Export Trial Balance CSV</span>
                    </a>
                  </div>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Database Schema &amp; Table Inspector</h3>
                  <span className="eyebrow">
                    Click any table row to inspect its live records below
                  </span>
                </div>
                <div className="card__body">
                  {dbLoading && <div className="empty">Inspecting databases…</div>}
                  {dbInfo && (
                    <table className="ledger">
                      <thead>
                        <tr>
                          <th>Store</th>
                          <th>Table name</th>
                          <th>Role</th>
                          <th>Description</th>
                          <th className="num">Rows</th>
                          <th className="num">Inspect</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dbInfo.tables.map((t) => (
                          <tr
                            key={t.name}
                            className={`profile-row ${
                              selectedTable === t.name ? "profile-row--active" : ""
                            }`}
                            onClick={() => setSelectedTable(t.name)}
                          >
                            <td>
                              <span
                                className={`pill pill--sm ${
                                  t.store === "oltp" ? "pill--credit" : "pill--statutory"
                                }`}
                              >
                                {t.store.toUpperCase()}
                              </span>
                            </td>
                            <td className="fig">
                              <strong>{t.name}</strong>
                            </td>
                            <td className="muted">{t.role}</td>
                            <td className="muted">{t.description}</td>
                            <td className="num fig">{t.row_count.toLocaleString()}</td>
                            <td className="num">
                              <button
                                type="button"
                                className="btn btn--sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedTable(t.name);
                                }}
                              >
                                {selectedTable === t.name ? "Viewing" : "Preview"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>

              {/* Live Table Row Previewer */}
              <section className="card">
                <div className="card__head">
                  <h3>
                    Table Preview: <code className="fig">{selectedTable}</code>
                  </h3>
                  <span className="eyebrow">
                    {preview
                      ? `Showing ${preview.rows.length} of ${preview.total_rows} total rows (${preview.store.toUpperCase()})`
                      : "Loading preview…"}
                  </span>
                </div>
                <div className="card__body ledger-scroll">
                  {previewLoading && <div className="empty">Reading rows from {selectedTable}…</div>}
                  {!previewLoading && preview && preview.rows.length === 0 && (
                    <div className="empty">Table `{selectedTable}` is currently empty (0 rows).</div>
                  )}
                  {!previewLoading && preview && preview.rows.length > 0 && (
                    <table className="ledger">
                      <thead>
                        <tr>
                          {preview.columns.map((col) => (
                            <th key={col} className="fig">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row, rIdx) => (
                          <tr key={rIdx}>
                            {preview.columns.map((col) => (
                              <td key={col} className="fig" style={{ fontSize: 12.5 }}>
                                {row[col] === null || row[col] === undefined
                                  ? "NULL"
                                  : String(row[col])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>
            </div>
          )}

          {/* ==================== 5. RESET ==================== */}
          {activeSection === "reset" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="card">
                <div className="card__head">
                  <h3>Reset UI &amp; Application Preferences</h3>
                  <span className="pill">Browser Storage</span>
                </div>
                <div className="card__body">
                  <div className="settings-row">
                    <div>
                      <strong>Restore factory UI settings</strong>
                      <p className="muted settings-row__sub">
                        Resets theme (System), density (Comfortable), viewport preset (Responsive),
                        accessibility options, and section period filters to their defaults without
                        touching your financial database.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        resetPreferences();
                        showNotice("Restored all UI and application preferences to defaults.");
                      }}
                    >
                      <IconSettings size={15} />
                      <span>Reset Preferences</span>
                    </button>
                  </div>
                </div>
              </section>

              <section className="card">
                <div className="card__head">
                  <h3>Reset Database to Clean Baseline</h3>
                  <span className="pill pill--statutory">Automatic SQLite Backup</span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Clean 36-account zero-balance baseline</strong>
                      <p className="muted settings-row__sub">
                        Creates a verified SQLite backup in <code>backend/backups/</code>, removes all
                        journal entries, budgets, payees, and salary profiles, restores the 36
                        built-in Philippine Chart of Accounts with ₱0.00 opening balances, and
                        rebuilds the DuckDB warehouse.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={resetBaseline.isPending}
                      onClick={handleResetBaseline}
                    >
                      <IconRefresh size={15} />
                      <span>
                        {resetBaseline.isPending ? "Resetting…" : "Reset to Clean Baseline"}
                      </span>
                    </button>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Populate 4-month demo ledger</strong>
                      <p className="muted settings-row__sub">
                        After a clean reset, load the sample Filipino breadwinner dataset (opening
                        balances, monthly payslips, everyday expenses, transfers, and budgets).
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn"
                      disabled={seedDemo.isPending}
                      onClick={handleSeedDemo}
                    >
                      <IconDatabase size={15} />
                      <span>{seedDemo.isPending ? "Loading demo…" : "Load Demo Dataset"}</span>
                    </button>
                  </div>
                </div>
              </section>
            </div>
          )}

          {/* ==================== 6. DATA DELETION ==================== */}
          {activeSection === "deletion" && (
            <div className="grid" style={{ gap: 20 }}>
              <section className="card">
                <div className="card__head">
                  <h3>Granular Data Deletion</h3>
                  <span className="eyebrow">
                    Each action creates a safety SQLite backup and refreshes the DuckDB warehouse
                  </span>
                </div>
                <div className="card__body settings-rows">
                  <div className="settings-row">
                    <div>
                      <strong>Delete all journal entries &amp; lines</strong>
                      <p className="muted settings-row__sub">
                        Permanently removes all recorded transactions (including voided entries) while
                        keeping your accounts, payees, budgets, and salary profiles intact.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn--danger-outline"
                      disabled={deleteData.isPending}
                      onClick={() => handleDeleteTarget("entries", "all journal entries")}
                    >
                      <IconTrash size={15} />
                      <span>Clear Journal Entries</span>
                    </button>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Delete all budgets &amp; fund overrides</strong>
                      <p className="muted settings-row__sub">
                        Clears all monthly expense account limits and starting-balance overrides.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn--danger-outline"
                      disabled={deleteData.isPending}
                      onClick={() =>
                        handleDeleteTarget("budgets", "all budgets and fund overrides")
                      }
                    >
                      <IconTrash size={15} />
                      <span>Clear Budgets</span>
                    </button>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Delete saved salary profiles</strong>
                      <p className="muted settings-row__sub">
                        Removes all saved salary calculation snapshots and clears{" "}
                        <code>fact_payslip_item</code> in the warehouse (posted ledger payslips remain).
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn--danger-outline"
                      disabled={deleteData.isPending}
                      onClick={() =>
                        handleDeleteTarget("salary_profiles", "all saved salary profiles")
                      }
                    >
                      <IconTrash size={15} />
                      <span>Clear Salary Profiles</span>
                    </button>
                  </div>

                  <div className="settings-row">
                    <div>
                      <strong>Delete custom accounts &amp; payees</strong>
                      <p className="muted settings-row__sub">
                        Removes all saved payees and user-created custom accounts (archives any custom
                        account referenced by existing entries).
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn--danger-outline"
                      disabled={deleteData.isPending}
                      onClick={() =>
                        handleDeleteTarget(
                          "custom_accounts_payees",
                          "custom accounts and saved payees",
                        )
                      }
                    >
                      <IconTrash size={15} />
                      <span>Clear Custom Accounts &amp; Payees</span>
                    </button>
                  </div>
                </div>
              </section>

              <section className="card card--danger">
                <div className="card__head">
                  <h3>Danger Zone: Wipe All Financial Data</h3>
                  <span className="pill pill--debit">Irreversible without backup restore</span>
                </div>
                <div className="card__body">
                  <p className="muted" style={{ marginTop: 0 }}>
                    This wipes every journal entry, line, budget, fund override, payee, salary
                    profile, and custom account, leaving only the 36 zero-balance system accounts.
                    Type <code className="fig">DELETE</code> below to unlock the button.
                  </p>
                  <div className="form-row">
                    <label className="field">
                      <span className="eyebrow">Type DELETE to confirm</span>
                      <input
                        value={deleteConfirmText}
                        onChange={(e) => setDeleteConfirmText(e.target.value)}
                        placeholder="DELETE"
                      />
                    </label>
                    <button
                      type="button"
                      className="btn btn--danger"
                      disabled={deleteConfirmText !== "DELETE" || deleteData.isPending}
                      onClick={() => handleDeleteTarget("all_financial", "ALL financial data")}
                    >
                      <IconTrash size={15} />
                      <span>Wipe All Financial Data</span>
                    </button>
                  </div>
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
