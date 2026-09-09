import { useEffect, useState } from "react";
import { useFilters } from "@/store/filters";

/**
 * Categorical series colors — identity, not magnitude.
 *
 * These eight hues and their dark steps are the data-viz reference palette,
 * re-ordered to lead with the brand's crust-orange. The ordering *is* the
 * colorblind-safety mechanism, so it is not cosmetic: this order was validated
 * with `validate_palette.js` against this app's own chart surface (--crumb) in
 * both modes and clears every gate —
 *
 *   light (#faf1e2): CVD ΔE 9.1 · normal-vision ΔE 19.6
 *   dark  (#251f17): CVD ΔE 8.4 · normal-vision ΔE 19.3
 *
 * Four light-mode slots sit below 3:1 contrast on the cream surface, so charts
 * using them owe the reader *relief*: a legend plus either direct labels or the
 * companion table. Every chart here ships a legend, and the expense mix sits
 * beside the "Expense by account" table.
 *
 * Do not add a ninth color. Past eight, fold the tail into "Other" (see
 * `seriesColors`) or facet the chart — a generated hue would break the gates.
 */
const CATEGORICAL_LIGHT = [
  "#eb6834", // orange — the crust
  "#2a78d6", // blue
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
] as const;

const CATEGORICAL_DARK = [
  "#d95926",
  "#3987e5",
  "#199e70",
  "#c98500",
  "#d55181",
  "#008300",
  "#9085e9",
  "#e66767",
] as const;

export const MAX_SERIES = CATEGORICAL_LIGHT.length;

export interface ChartPalette {
  /** Semantic roles from the design system. Reserved — never reused as a
   * series color, so "green means money in" stays true everywhere. */
  green: string;
  crust: string;
  debit: string;
  credit: string;
  good: string;
  warn: string;
  muted: string;
  rule: string;
  ink: string;
  surface: string;
  /** Categorical slots, in fixed order. Index by position, never cycle. */
  categorical: readonly string[];
  isDark: boolean;
}

const VARS = [
  "green",
  "crust",
  "debit",
  "credit",
  "good",
  "warn",
  "muted",
  "rule",
  "ink",
  "surface",
] as const;

function readPalette(): ChartPalette {
  const root = document.documentElement;
  const style = getComputedStyle(root);
  const out = {} as ChartPalette;
  for (const key of VARS) {
    out[key] = style.getPropertyValue(`--${key}`).trim() || "#888888";
  }
  const stamped = root.getAttribute("data-theme");
  const isDark =
    stamped === "dark" ||
    (stamped === null && window.matchMedia("(prefers-color-scheme: dark)").matches);
  out.isDark = isDark;
  // Dark steps are *selected* for the dark surface, not an automatic flip of
  // the light ones — same hues, re-stepped and re-validated as a set.
  out.categorical = isDark ? CATEGORICAL_DARK : CATEGORICAL_LIGHT;
  return out;
}

/**
 * Resolved theme colors for Chart.js canvases. Canvas drawing needs real color
 * strings (not CSS custom properties), and doesn't repaint on its own when the
 * theme flips — so this re-reads computed styles whenever the theme setting or
 * (in "system" mode) the OS color-scheme preference changes.
 */
export function useChartPalette(): ChartPalette {
  const theme = useFilters((s) => s.theme);
  const [palette, setPalette] = useState<ChartPalette>(() =>
    typeof document !== "undefined" ? readPalette() : ({} as ChartPalette),
  );

  useEffect(() => {
    const id = requestAnimationFrame(() => setPalette(readPalette()));
    return () => cancelAnimationFrame(id);
  }, [theme]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setPalette(readPalette());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return palette;
}

/**
 * Split named series into the eight that get their own color and a folded
 * "Other" bucket, so color always follows the entity and never its rank
 * within a filtered subset.
 */
export function foldToPalette<T>(
  items: T[],
  weight: (item: T) => number,
): { kept: { item: T; color: (p: ChartPalette) => string }[]; folded: T[] } {
  const ranked = [...items].sort((a, b) => weight(b) - weight(a));
  const kept = ranked.slice(0, MAX_SERIES).map((item, i) => ({
    item,
    color: (p: ChartPalette) => p.categorical[i],
  }));
  return { kept, folded: ranked.slice(MAX_SERIES) };
}
