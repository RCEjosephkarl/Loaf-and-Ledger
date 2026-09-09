import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * The story behind a heading, one hover away.
 *
 * Every page and most cards used to lead with a paragraph explaining
 * themselves, which pushed the actual figures below the fold. The prose is
 * worth keeping — it is how someone learns what double-entry is doing on
 * their behalf — so it moves in here instead of being cut.
 *
 * Hover is the fast path, but it can't be the only one: the note opens on
 * focus for keyboard users and pins open on click for touch, where there is
 * no hover at all.
 */
export function InfoNote({
  label,
  lead,
  children,
}: {
  /** Accessible name, e.g. "About accounts". */
  label: string;
  /** The one-line narrative title this note replaced. */
  lead?: string;
  children: ReactNode;
}) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const panelId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);

  const open = hovered || pinned;

  // A pinned note stays up until it is dismissed, so it needs the two escapes
  // people expect from an open popover: Escape, and a click elsewhere.
  useEffect(() => {
    if (!pinned) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPinned(false);
    };
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setPinned(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [pinned]);

  return (
    <span
      className="infonote"
      ref={wrapRef}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        className="infonote__btn"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? panelId : undefined}
        onClick={() => setPinned((p) => !p)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
      >
        <span aria-hidden>i</span>
      </button>
      {open && (
        <span className="infonote__panel" id={panelId} role="tooltip">
          {lead && <span className="infonote__lead">{lead}</span>}
          {children}
        </span>
      )}
    </span>
  );
}
