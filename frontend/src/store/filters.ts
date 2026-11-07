import { create } from "zustand";
import { persist } from "zustand/middleware";
import { localISODate } from "@/lib/format";

export type TimeRange = "this_month" | "last_3m" | "ytd" | "all";
export type Theme = "light" | "dark" | "system";

/** Single source of the range presets + their display labels, shared by
 * the section period control and any page/card that needs to describe
 * the currently selected scope. */
export const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_3m", label: "Last 3 mo" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

export function timeRangeLabel(range: TimeRange): string {
  return TIME_RANGES.find((r) => r.value === range)?.label ?? range;
}

export type PeriodSection = "dashboard" | "accounts" | "analytics";
export type DateBounds = { start?: string | null; end?: string | null };
const DEFAULT_PERIODS: Record<PeriodSection, TimeRange> = {
  dashboard: "this_month", accounts: "this_month", analytics: "this_month",
};

export interface FilterState {
  periods: Record<PeriodSection, TimeRange>;
  theme: Theme;
  setPeriod: (section: PeriodSection, range: TimeRange) => void;
  setTheme: (theme: Theme) => void;
}

export const useFilters = create<FilterState>()(
  persist(
    (set) => ({
      periods: { ...DEFAULT_PERIODS },
      theme: "system",
      setPeriod: (section, range) => set((state) => ({
        periods: { ...state.periods, [section]: range },
      })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "loaf-ledger-filters",
      version: 3,
      partialize: (state) => ({ theme: state.theme, periods: state.periods }),
      migrate: (persisted) => {
        const old = persisted as { theme?: Theme } | undefined;
        return { theme: old?.theme ?? "system", periods: { ...DEFAULT_PERIODS } };
      },
    },
  ),
);

export function useSectionPeriod(section: PeriodSection) {
  const range = useFilters((state) => state.periods[section]);
  const setPeriod = useFilters((state) => state.setPeriod);
  return [range, (value: TimeRange) => setPeriod(section, value)] as const;
}

/** Resolve a time-range preset to inclusive ISO start/end (or nulls for "all"). */
export function rangeBounds(range: TimeRange): { start: string | null; end: string | null } {
  const now = new Date();
  const iso = localISODate;
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  switch (range) {
    case "this_month":
      return { start: iso(new Date(now.getFullYear(), now.getMonth(), 1)), end: iso(endOfMonth) };
    case "last_3m":
      return {
        start: iso(new Date(now.getFullYear(), now.getMonth() - 2, 1)),
        end: iso(endOfMonth),
      };
    case "ytd":
      return { start: iso(new Date(now.getFullYear(), 0, 1)), end: iso(now) };
    case "all":
      return { start: null, end: null };
  }
}

/**
 * The period of equal length immediately preceding the current range — used
 * for the "vs prior period" comparison. Null for "all", since an open-ended
 * range has no natural predecessor.
 */
export function previousRangeBounds(range: TimeRange): { start: string; end: string } | null {
  const current = rangeBounds(range);
  if (!current.start || !current.end) return null;
  const iso = localISODate;
  const daySpan =
    Math.round(
      (new Date(current.end).getTime() - new Date(current.start).getTime()) / 86_400_000,
    ) + 1;
  const prevEnd = new Date(current.start);
  prevEnd.setDate(prevEnd.getDate() - 1);
  const prevStart = new Date(prevEnd);
  prevStart.setDate(prevStart.getDate() - (daySpan - 1));
  return { start: iso(prevStart), end: iso(prevEnd) };
}
