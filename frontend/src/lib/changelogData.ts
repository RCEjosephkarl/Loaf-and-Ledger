export interface ChangelogItem {
  category: "Added" | "Changed" | "Fixed" | "Removed";
  title: string;
  detail: string;
}

export interface ChangelogRelease {
  version: string;
  date: string;
  badge?: string;
  summary: string;
  items: ChangelogItem[];
}

export const CHANGELOG_RELEASES: ChangelogRelease[] = [
  {
    version: "Unreleased",
    date: "2026-11",
    badge: "Latest",
    summary:
      "Modernized collapsible navigation rail, Welcome Hub, Global Settings suite, responsive viewport presets, independent section periods, and fortnightly payroll.",
    items: [
      {
        category: "Added",
        title: "Modern Navigation Rail & Top Header",
        detail:
          "Replaced the static sidebar with a collapsible icon-and-label navigation rail, bottom mobile navigation bar, and glassmorphic top command header.",
      },
      {
        category: "Added",
        title: "Global Settings & Database Inspector",
        detail:
          "Added /settings and quick slide-over drawer covering Appearance, Default Values, Accessibility, live OLTP/OLAP Database Navigation & Table Preview, Clean Baseline Reset, and granular Data Deletion.",
      },
      {
        category: "Added",
        title: "Welcome Hub & Viewport Presets",
        detail:
          "Added interactive Welcome page with Changelogs and About views, plus live Desktop (1440px), Tablet Landscape (1024×768), and Mobile (390×844) viewport presets.",
      },
      {
        category: "Added",
        title: "Section periods & Fortnightly salaries",
        detail:
          "Dashboard, Accounts, and Analytics each persist independent period scopes. Added fortnightly (26 periods/year) payroll calculation and deduction percentage columns.",
      },
      {
        category: "Added",
        title: "Ledger pagination & Account period activity",
        detail:
          "Paginated ledger entries with full-history running cash balances, plus date-bounded debit/credit activity on the chart of accounts.",
      },
      {
        category: "Fixed",
        title: "Periodic rounding & Warehouse active profile sync",
        detail:
          "Derived periodic net pay from rounded period deductions so displayed net pay and ledger deposits match to the cent.",
      },
    ],
  },
  {
    version: "v0.2.0",
    date: "2026-09-09",
    badge: "Architecture",
    summary:
      "Structural rewrite: double-entry OLTP journal, DuckDB star-schema OLAP warehouse with write-through ETL, single-currency PHP focus, and four-act Analytics narrative.",
    items: [
      {
        category: "Added",
        title: "Double-entry OLTP Journal",
        detail:
          "Introduced the 36-account Philippine chart of accounts, payees, journal_entries, and journal_lines with strict SUM(debit) = SUM(credit) invariants.",
      },
      {
        category: "Added",
        title: "DuckDB OLAP Star Schema & Write-Through ETL",
        detail:
          "Dedicated analytical warehouse (dim_date, dim_account, dim_payee, dim_source, fact_ledger_line, fact_payslip_item, agg_monthly_account, agg_daily_cashflow) updated synchronously on every write.",
      },
      {
        category: "Added",
        title: "One-Click Idempotent Payslip Posting",
        detail:
          "Posts a saved salary breakdown as a single balanced multi-line journal entry: gross credited to income, statutory deductions debited, and net pay banked.",
      },
      {
        category: "Changed",
        title: "Four-Act Analytics Narrative",
        detail:
          "Rebuilt Analytics around four sequential questions — What came in, Where it went, What's left, and What it means — with a gross-to-net WaterfallChart.",
      },
      {
        category: "Fixed",
        title: "Transfers vs. Spending Separation",
        detail:
          "Transfers between balance-sheet accounts are flagged is_transfer and excluded from expense totals so moving money into savings never distorts your savings rate.",
      },
    ],
  },
  {
    version: "v0.1.0",
    date: "2026-07-06",
    summary:
      "Budgeting periods, initial fund carryover overrides, stacked monthly category charts, and timezone-safe local date bounds.",
    items: [
      {
        category: "Added",
        title: "Budget Periods & Initial Fund",
        detail:
          "Added multi-month budget scopes and period starting balance tracking with automatic carryover and manual overrides.",
      },
      {
        category: "Added",
        title: "Dashboard Highlight Card & Deterministic Insights",
        detail:
          "Emphasized the primary Balance sheet card and expanded rule-based insights for spending concentration and cashflow.",
      },
      {
        category: "Fixed",
        title: "Local Timezone Date Boundaries",
        detail:
          "Replaced UTC toISOString() date slicing with local calendar components so UTC+8 Philippine evenings never shift period boundaries by a day.",
      },
    ],
  },
  {
    version: "v0.0.0",
    date: "2026-07-06",
    summary:
      "Inaugural slice: strategy-pattern Philippine tax engine, ledger recording, budget tracking, CSV export, and FastAPI + React foundation.",
    items: [
      {
        category: "Added",
        title: "Statutory Payroll Tax Engine (F1)",
        detail:
          "Implemented Philippine TRAIN law income tax brackets after mandatory SSS, PhilHealth, and Pag-IBIG contributions.",
      },
      {
        category: "Added",
        title: "Core Bookkeeping, Budgets & CSV Exports (F2–F6)",
        detail:
          "Initial transaction ledger, monthly category budgets, streamed CSV exports, and FastAPI + SQLAlchemy 2.0 + React + TanStack Query stack.",
      },
    ],
  },
];

export const APP_PILLARS = [
  {
    numeral: "01",
    title: "PH Statutory Payroll Math",
    description:
      "Computes mandatory SSS, PhilHealth, and Pag-IBIG contributions first, deducts them from gross pay, and applies progressive Philippine TRAIN law tax brackets.",
  },
  {
    numeral: "02",
    title: "Provable Double-Entry Books",
    description:
      "Every movement of money is a journal entry whose debits equal its credits. Balances are derived from the journal alone and verified by the Trial Balance.",
  },
  {
    numeral: "03",
    title: "Moving vs. Spending Money",
    description:
      "Transferring ₱5,000 from payroll to savings or GCash hits two asset accounts — structurally marked as a transfer so saving is never miscounted as an expense.",
  },
  {
    numeral: "04",
    title: "Dual-Store OLTP + OLAP Architecture",
    description:
      "SQLite/PostgreSQL acts as the transactional system of record while a DuckDB star-schema warehouse powers instant multi-month analytics via write-through ETL.",
  },
];
