import { useRef, useState, type ReactNode } from "react";

export interface HoverTab {
  id: string;
  label: string;
  content: ReactNode;
}

/**
 * Tab strip that switches its panel on hover (debounced, so passing over
 * intermediate tabs on the way to another doesn't flicker), and "pins" a
 * tab on click so it stops reverting once the mouse leaves. Reuses the
 * existing `.seg`/`.seg--on` segmented-button look.
 */
export function HoverTabs({
  tabs,
  defaultTabId,
  hoverDelayMs = 150,
}: {
  tabs: HoverTab[];
  defaultTabId?: string;
  hoverDelayMs?: number;
}) {
  const [pinned, setPinned] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const active = pinned ?? hovered ?? defaultTabId ?? tabs[0]?.id;

  const scheduleHover = (id: string) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setHovered(id), hoverDelayMs);
  };

  const onStripLeave = () => {
    clearTimeout(timer.current);
    setHovered(null);
  };

  const onKeyDown = (e: React.KeyboardEvent, i: number) => {
    if (e.key === "ArrowRight") setPinned(tabs[(i + 1) % tabs.length].id);
    if (e.key === "ArrowLeft") setPinned(tabs[(i - 1 + tabs.length) % tabs.length].id);
  };

  return (
    <div className="hover-tabs">
      <div className="hover-tabs__strip" role="tablist" onMouseLeave={onStripLeave}>
        {tabs.map((t, i) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active === t.id}
            tabIndex={0}
            className={`seg ${active === t.id ? "seg--on" : ""}`}
            onMouseEnter={() => scheduleHover(t.id)}
            onFocus={() => scheduleHover(t.id)}
            onClick={() => setPinned(t.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="hover-tabs__panel" role="tabpanel">
        {tabs.find((t) => t.id === active)?.content}
      </div>
    </div>
  );
}
