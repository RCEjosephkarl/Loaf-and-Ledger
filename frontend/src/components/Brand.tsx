/** Loaf & Ledger mark: a scored loaf with a wheat sprig, resting on a ledger rule. */
export function Brand({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path
        d="M5 17c0-4.4 4.9-7 11-7s11 2.6 11 7v1.5a1.5 1.5 0 0 1-1.5 1.5h-19A1.5 1.5 0 0 1 5 18.5V17Z"
        fill="var(--crust)"
      />
      <path
        d="M11 11.5c0 2-1 3.2-1 5M16 10.6c0 2.2-1 3.4-1 5.4M21 11.5c0 2-1 3.2-1 5"
        stroke="var(--surface)"
        strokeWidth="1.3"
        strokeLinecap="round"
        opacity="0.75"
      />
      {/* wheat sprig accent */}
      <g stroke="var(--warn)" strokeWidth="1.1" strokeLinecap="round" opacity="0.85">
        <line x1="25" y1="10" x2="27" y2="2" />
        <line x1="25.3" y1="8.2" x2="22.5" y2="5.3" />
        <line x1="25.3" y1="8.2" x2="28.2" y2="6.2" />
        <line x1="25.7" y1="5.6" x2="23.3" y2="3.2" />
        <line x1="25.7" y1="5.6" x2="28" y2="3.6" />
      </g>
      <line x1="4" y1="24" x2="28" y2="24" stroke="var(--ink-soft)" strokeWidth="2" strokeLinecap="round" opacity="0.55" />
      <line x1="4" y1="26.5" x2="28" y2="26.5" stroke="var(--ink-soft)" strokeWidth="1" strokeLinecap="round" opacity="0.35" />
    </svg>
  );
}
