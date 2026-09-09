import { money } from "@/lib/format";

/** A monetary figure in the ledger's monospace tabular style, optionally
 * tinted by which side of the books it sits on. */
export function Money({
  value,
  sign,
}: {
  value: string | number;
  sign?: "credit" | "debit";
}) {
  const cls = sign ? `fig fig--${sign}` : "fig";
  return <span className={cls}>{money(value)}</span>;
}
