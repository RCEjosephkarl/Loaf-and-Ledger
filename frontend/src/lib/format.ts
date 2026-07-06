export const CURRENCIES = ["USD", "PHP", "AUD", "EUR"] as const;

export function money(value: string | number, currency: string): string {
  const n = typeof value === "string" ? Number(value) : value;
  try {
    return new Intl.NumberFormat("en", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

export function percent(value: string | number, digits = 0): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${(n * 100).toFixed(digits)}%`;
}

export function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en", { month: "short", year: "2-digit" });
}

/** Parse a "YYYY-MM-DD" date as local time (avoids UTC-parse day-shift) and format e.g. "Jul 3". */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en", { month: "short", day: "numeric" });
}

/**
 * Format a local Date as "YYYY-MM-DD" without going through UTC. The mirror
 * image of `shortDate`'s local-time parse: `Date#toISOString` renders in
 * UTC, which silently shifts date-only boundaries by a day for timezones
 * ahead of UTC (e.g. PH/UTC+8) — always build date-only strings from local
 * Y/M/D components instead.
 */
export function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** "14:32:00" (or "14:32") -> "14:32"; null/undefined -> "—". */
export function formatTime(t: string | null | undefined): string {
  return t ? t.slice(0, 5) : "—";
}

/** Signed percent for change-over-time figures, e.g. 0.12 -> "+12%", -0.08 -> "-8%". */
export function signedPercent(value: number, digits = 0): string {
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}
