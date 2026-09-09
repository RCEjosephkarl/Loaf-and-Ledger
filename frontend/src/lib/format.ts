/** The app is single-currency. One constant, one place to change it. */
export const CURRENCY = "PHP";

export function money(value: string | number, currency: string = CURRENCY): string {
  const n = typeof value === "string" ? Number(value) : value;
  try {
    return new Intl.NumberFormat("en-PH", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

/** Compact form for axis ticks and dense tables: ₱32.0k, ₱1.2M. */
export function moneyShort(value: string | number): string {
  const n = Math.abs(typeof value === "string" ? Number(value) : value);
  const sign = Number(value) < 0 ? "-" : "";
  if (n >= 1_000_000) return `${sign}₱${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${sign}₱${(n / 1_000).toFixed(n >= 100_000 ? 0 : 1)}k`;
  return `${sign}₱${n.toFixed(0)}`;
}

export function percent(value: string | number, digits = 0): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${(n * 100).toFixed(digits)}%`;
}

/** "2026-06" -> "Jun '26". The apostrophe matters: a bare "Jun 26" reads as
 * the 26th of June on an axis that is otherwise full of dates. */
export function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  const month = new Date(y, m - 1, 1).toLocaleDateString("en", { month: "short" });
  return `${month} '${String(y).slice(2)}`;
}

/** Parse a "YYYY-MM-DD" date as local time (avoids UTC-parse day-shift) and format e.g. "Jul 3". */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en", { month: "short", day: "numeric" });
}

/**
 * Format a local Date as "YYYY-MM-DD" without going through UTC. `toISOString`
 * renders in UTC, which silently shifts date-only boundaries by a day for
 * timezones ahead of UTC — PH is UTC+8, so this matters here every evening.
 */
export function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Local "YYYY-MM-DDTHH:MM" for the datetime the API stores on an entry. */
export function localISODateTime(d: Date): string {
  return `${localISODate(d)}T${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes(),
  ).padStart(2, "0")}`;
}

/** "2026-06-15T19:30:00" -> "19:30"; empty -> "—". */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = iso.includes("T") ? iso.split("T")[1] : iso;
  return t.slice(0, 5);
}

/** "2026-06-15T19:30:00" -> "Jun 15". */
export function entryDate(iso: string): string {
  return shortDate(iso.slice(0, 10));
}

/** Signed percent for change-over-time figures, e.g. 0.12 -> "+12%". */
export function signedPercent(value: number, digits = 0): string {
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

/** Human label for an account type, used in group headings. */
export const ACCOUNT_TYPE_LABEL: Record<string, string> = {
  asset: "Assets",
  liability: "Liabilities",
  equity: "Equity",
  income: "Income",
  expense: "Expenses",
};

/** Display order for the chart of accounts — balance sheet before P&L. */
export const ACCOUNT_TYPE_ORDER = ["asset", "liability", "equity", "income", "expense"] as const;
