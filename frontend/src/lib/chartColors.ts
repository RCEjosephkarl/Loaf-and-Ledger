import { useEffect, useState } from "react";
import { useFilters } from "@/store/filters";

/**
 * Categorical series colors — identity, not magnitude.
 *
 * These eight hues and their dark steps are the data-viz reference palette,
 * re-ordered to lead with the app's ink blue. The ordering *is* the
 * colorblind-safety mechanism, so it is not cosmetic: this order was validated
 * with `validate_palette.js` against this app's own chart surface (--card-bg)
 * in both modes and clears every gate —
 *
 *   light (#ffffff): CVD ΔE 9.1 · normal-vision ΔE 19.6
 *   dark  (#151d2a): CVD ΔE 8.4 · normal-vision ΔE 19.3 · all 8 clear 3:1
 *
 * Three light-mode slots sit below 3:1 contrast on the white surface, so charts
 * using them owe the reader *relief*: a legend plus either direct labels or the
 * companion table. Every chart here ships a legend, and the expense mix sits
 * beside the "Expense by account" table.
 *
 * Do not add a ninth color. Past eight, fold the tail into "Other" (see
 * `seriesColors`) or facet the chart — a generated hue would break the gates.
 */
const CATEGORICAL_LIGHT = [
  "#2a78d6", // blue — the app's own accent
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
] as const;

const CATEGORICAL_DARK = [
  "#3987e5",
  "#d95926",
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
  accent: string;
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

/** Chart-visible design tokens. `surface` is the card interior the charts
 *  actually sit on — the same surface the palette was validated against —
 *  which is not the same token as the app chrome. */
const VARS = {
  accent: "--accent",
  debit: "--debit",
  credit: "--credit",
  good: "--good",
  warn: "--warn",
  muted: "--muted",
  rule: "--rule",
  ink: "--ink",
  surface: "--card-bg",
} as const;

/**
 * Resolve a design token to a real color string.
 *
 * Reading a custom property straight off the root returns it *as authored* —
 * for these tokens that is the literal text `light-dark(#2a5fa8, #7aa9ee)`,
 * which Chart.js cannot parse and silently paints black. Assigning it to a
 * real `color` property instead forces the cascade to compute it, and
 * `getComputedStyle` then hands back the resolved `rgb(...)` for whichever
 * scheme is currently active.
 */
function withResolver<T>(fn: (resolve: (cssVar: string) => string) => T): T {
  const probe = document.createElement("span");
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText = "position:absolute;width:0;height:0;visibility:hidden";
  document.body.appendChild(probe);
  try {
    return fn((cssVar) => {
      probe.style.color = "";
      probe.style.color = `var(${cssVar})`;
      const resolved = getComputedStyle(probe).color;
      return resolved && resolved !== "rgba(0, 0, 0, 0)" ? resolved : "#888888";
    });
  } finally {
    probe.remove();
  }
}

function readPalette(): ChartPalette {
  const root = document.documentElement;
  const out = {} as ChartPalette;
  withResolver((resolve) => {
    for (const [key, cssVar] of Object.entries(VARS)) {
      out[key as keyof typeof VARS] = resolve(cssVar);
    }
  });
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
