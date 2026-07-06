import { create } from "zustand";
import { persist } from "zustand/middleware";
import { localISODate } from "@/lib/format";
import type { Region } from "@/lib/types";

export type TimeRange = "this_month" | "last_3m" | "ytd" | "all";
export type Theme = "light" | "dark" | "system";

/** Single source of the range presets + their display labels, shared by
 * FilterBar's segmented control and any page/card that needs to describe
 * the currently selected scope (e.g. Dashboard's FX chart title). */
export const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_3m", label: "Last 3 mo" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

export function timeRangeLabel(range: TimeRange): string {
  return TIME_RANGES.find((r) => r.value === range)?.label ?? range;
}

export interface FilterState {
  // Global filters (F6) — cascade into F1 default region + all reads.
  region: Region | ""; // "" = all regions
  currency: string; // display currency (display-only conversion)
  timeRange: TimeRange;
  theme: Theme;
  setRegion: (r: Region | "") => void;
  setCurrency: (c: string) => void;
  setTimeRange: (t: TimeRange) => void;
  setTheme: (t: Theme) => void;
}

export const useFilters = create<FilterState>()(
  persist(
    (set) => ({
      region: "",
      currency: "USD",
      timeRange: "this_month",
      theme: "system",
      setRegion: (region) => set({ region }),
      setCurrency: (currency) => set({ currency }),
      setTimeRange: (timeRange) => set({ timeRange }),
      setTheme: (theme) => set({ theme }),
    }),
    { name: "loaf-ledger-filters" },
  ),
);

/** Resolve a time-range preset to inclusive ISO start/end (or nulls for "all"). */
export function rangeBounds(range: TimeRange): { start: string | null; end: string | null } {
  const now = new Date();
  const iso = localISODate;
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  switch (range) {
    case "this_month":
      return { start: iso(new Date(now.getFullYear(), now.getMonth(), 1)), end: iso(endOfMonth) };
    case "last_3m":
      return { start: iso(new Date(now.getFullYear(), now.getMonth() - 2, 1)), end: iso(endOfMonth) };
    case "ytd":
      return { start: iso(new Date(now.getFullYear(), 0, 1)), end: iso(now) };
    case "all":
      return { start: null, end: null };
  }
}

/**
 * The period of equal length immediately preceding the current range — used
 * for the "vs prior period" inflation/deflation comparison. Null for "all"
 * since an open-ended range has no natural predecessor.
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
