import { money } from "@/lib/format";

export function Money({
  value,
  currency,
  sign = "plain",
}: {
  value: string | number;
  currency: string;
  sign?: "credit" | "debit" | "plain";
}) {
  const cls = sign === "credit" ? "fig fig--credit" : sign === "debit" ? "fig fig--debit" : "fig";
  return <span className={cls}>{money(value, currency)}</span>;
}
