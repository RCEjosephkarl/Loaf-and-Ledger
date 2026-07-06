import { useEffect, useState } from "react";
import { useFilters } from "@/store/filters";

export interface ChartPalette {
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
}

const VARS: (keyof ChartPalette)[] = [
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
];

function readPalette(): ChartPalette {
  const style = getComputedStyle(document.documentElement);
  const out = {} as ChartPalette;
  for (const key of VARS) {
    out[key] = style.getPropertyValue(`--${key}`).trim() || "#888888";
  }
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
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setPalette(readPalette());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  return palette;
}
