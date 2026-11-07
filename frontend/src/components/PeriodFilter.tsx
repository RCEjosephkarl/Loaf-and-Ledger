import { TIME_RANGES, type TimeRange } from "@/store/filters";

export function PeriodFilter({ value, onChange }: {
  value: TimeRange; onChange: (range: TimeRange) => void;
}) {
  return (
    <div className="period-filter">
      <span className="eyebrow">Period</span>
      <div className="filterbar__segment" role="group" aria-label="Period">
        {TIME_RANGES.map((range) => (
          <button key={range.value} type="button"
            className={`seg ${value === range.value ? "seg--on" : ""}`}
            aria-pressed={value === range.value} onClick={() => onChange(range.value)}>
            {range.label}
          </button>
        ))}
      </div>
    </div>
  );
}
