import type { ReactNode } from "react";

/**
 * A visually bolder card variant — filled background, larger figures —
 * reserved for the Dashboard's single most important figure. Every other
 * page keeps the plain `.card` look; don't reuse this elsewhere or it stops
 * meaning "the headline number."
 */
export function HighlightCard({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card highlight-card">
      <div className="card__head">
        <h3>{title}</h3>
        {eyebrow}
      </div>
      <div className="card__body">{children}</div>
    </section>
  );
}
