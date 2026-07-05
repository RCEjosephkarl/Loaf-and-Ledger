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
