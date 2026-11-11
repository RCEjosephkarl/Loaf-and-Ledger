import { create } from "zustand";
import { persist } from "zustand/middleware";
import { localISODate } from "@/lib/format";
import type { EntryKind, PayPeriod } from "@/lib/types";

export type TimeRange = "this_month" | "last_3m" | "ytd" | "all";
export type Theme = "light" | "dark" | "system";
export type Density = "comfortable" | "compact";
export type ViewportPreset = "responsive" | "desktop" | "tablet" | "mobile";
export type FontScale = "sm" | "md" | "lg";
export type LedgerPageSize = 10 | 20 | 50;

/** Single source of the range presets + their display labels, shared by
 * the section period control and any page/card that needs to describe
 * the currently selected scope. */
export const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_3m", label: "Last 3 mo" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

export const VIEWPORT_PRESETS: {
  value: ViewportPreset;
  label: string;
  shortLabel: string;
  dimensions: string;
}[] = [
  { value: "responsive", label: "Responsive (Auto)", shortLabel: "Auto", dimensions: "Fluid window" },
  { value: "desktop", label: "Desktop", shortLabel: "Desktop", dimensions: "1440 × 900" },
  { value: "tablet", label: "Tablet (Landscape)", shortLabel: "Tablet", dimensions: "1024 × 768" },
  { value: "mobile", label: "Mobile", shortLabel: "Mobile", dimensions: "390 × 844" },
];

export function timeRangeLabel(range: TimeRange): string {
  return TIME_RANGES.find((r) => r.value === range)?.label ?? range;
}

export type PeriodSection = "dashboard" | "accounts" | "analytics";
export type DateBounds = { start?: string | null; end?: string | null };
const DEFAULT_PERIODS: Record<PeriodSection, TimeRange> = {
  dashboard: "this_month",
  accounts: "this_month",
  analytics: "this_month",
};

export interface FilterState {
  // Section period filters
  periods: Record<PeriodSection, TimeRange>;

  // Appearance
  theme: Theme;
  density: Density;
  sidebarCollapsed: boolean;
  viewportPreset: ViewportPreset;
  showWelcomeOnLaunch: boolean;

  // Default values
  defaultPeriod: TimeRange;
  defaultPayPeriod: PayPeriod;
  defaultEntryKind: EntryKind;
  ledgerPageSize: LedgerPageSize;

  // Accessibility
  fontScale: FontScale;
  reducedMotion: boolean;
  highContrast: boolean;

  // Ephemeral session UI state (not persisted across full reloads so Welcome shows on launch)
  welcomeOpen: boolean;
  welcomeTab: "overview" | "changelogs" | "about";
  settingsDrawerOpen: boolean;

  // Actions
  setPeriod: (section: PeriodSection, range: TimeRange) => void;
  setTheme: (theme: Theme) => void;
  setDensity: (density: Density) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setViewportPreset: (preset: ViewportPreset) => void;
  setShowWelcomeOnLaunch: (show: boolean) => void;
  setDefaultPeriod: (range: TimeRange) => void;
  applyDefaultPeriodToAll: (range?: TimeRange) => void;
  setDefaultPayPeriod: (period: PayPeriod) => void;
  setDefaultEntryKind: (kind: EntryKind) => void;
  setLedgerPageSize: (size: LedgerPageSize) => void;
  setFontScale: (scale: FontScale) => void;
  setReducedMotion: (reduced: boolean) => void;
  setHighContrast: (high: boolean) => void;
  setWelcomeOpen: (open: boolean, tab?: "overview" | "changelogs" | "about") => void;
  setSettingsDrawerOpen: (open: boolean) => void;
  resetPreferences: () => void;
}

const INITIAL_PREFS = {
  periods: { ...DEFAULT_PERIODS },
  theme: "system" as Theme,
  density: "comfortable" as Density,
  sidebarCollapsed: false,
  viewportPreset: "responsive" as ViewportPreset,
  showWelcomeOnLaunch: true,
  defaultPeriod: "this_month" as TimeRange,
  defaultPayPeriod: "monthly" as PayPeriod,
  defaultEntryKind: "expense" as EntryKind,
  ledgerPageSize: 10 as LedgerPageSize,
  fontScale: "md" as FontScale,
  reducedMotion: false,
  highContrast: false,
};

export const useFilters = create<FilterState>()(
  persist(
    (set, get) => ({
      ...INITIAL_PREFS,
      welcomeOpen: true,
      welcomeTab: "overview",
      settingsDrawerOpen: false,

      setPeriod: (section, range) =>
        set((state) => ({
          periods: { ...state.periods, [section]: range },
        })),
      setTheme: (theme) => set({ theme }),
      setDensity: (density) => set({ density }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setViewportPreset: (viewportPreset) => set({ viewportPreset }),
      setShowWelcomeOnLaunch: (showWelcomeOnLaunch) => set({ showWelcomeOnLaunch }),
      setDefaultPeriod: (defaultPeriod) => set({ defaultPeriod }),
      applyDefaultPeriodToAll: (range) => {
        const target = range ?? get().defaultPeriod;
        set({
          defaultPeriod: target,
          periods: { dashboard: target, accounts: target, analytics: target },
        });
      },
      setDefaultPayPeriod: (defaultPayPeriod) => set({ defaultPayPeriod }),
      setDefaultEntryKind: (defaultEntryKind) => set({ defaultEntryKind }),
      setLedgerPageSize: (ledgerPageSize) => set({ ledgerPageSize }),
      setFontScale: (fontScale) => set({ fontScale }),
      setReducedMotion: (reducedMotion) => set({ reducedMotion }),
      setHighContrast: (highContrast) => set({ highContrast }),
      setWelcomeOpen: (welcomeOpen, tab) =>
        set((s) => ({
          welcomeOpen,
          welcomeTab: tab ?? s.welcomeTab,
        })),
      setSettingsDrawerOpen: (settingsDrawerOpen) => set({ settingsDrawerOpen }),
      resetPreferences: () =>
        set({
          ...INITIAL_PREFS,
        }),
    }),
    {
      name: "loaf-ledger-filters",
      version: 4,
      partialize: (state) => ({
        theme: state.theme,
        periods: state.periods,
        density: state.density,
        sidebarCollapsed: state.sidebarCollapsed,
        viewportPreset: state.viewportPreset,
        showWelcomeOnLaunch: state.showWelcomeOnLaunch,
        defaultPeriod: state.defaultPeriod,
        defaultPayPeriod: state.defaultPayPeriod,
        defaultEntryKind: state.defaultEntryKind,
        ledgerPageSize: state.ledgerPageSize,
        fontScale: state.fontScale,
        reducedMotion: state.reducedMotion,
        highContrast: state.highContrast,
      }),
      migrate: (persisted) => {
        const old = persisted as Partial<FilterState> | undefined;
        const showOnLaunch = old?.showWelcomeOnLaunch ?? true;
        return {
          ...INITIAL_PREFS,
          ...old,
          theme: old?.theme ?? "system",
          periods: old?.periods ?? { ...DEFAULT_PERIODS },
          welcomeOpen: showOnLaunch,
        };
      },
      onRehydrateStorage: () => (state) => {
        if (state && !state.showWelcomeOnLaunch) {
          state.setWelcomeOpen(false);
        }
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
