import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Region } from "@/lib/types";

export type TimeRange = "this_month" | "last_3m" | "ytd" | "all";
export type Theme = "light" | "dark" | "system";

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
  const iso = (d: Date) => d.toISOString().slice(0, 10);
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
