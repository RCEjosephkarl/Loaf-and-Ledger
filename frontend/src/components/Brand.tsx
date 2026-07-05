/** Loaf & Ledger mark: a scored loaf sitting on a ledger rule. */
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
      <line x1="4" y1="24" x2="28" y2="24" stroke="var(--green)" strokeWidth="2" strokeLinecap="round" />
      <line x1="4" y1="26.5" x2="28" y2="26.5" stroke="var(--green)" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}
