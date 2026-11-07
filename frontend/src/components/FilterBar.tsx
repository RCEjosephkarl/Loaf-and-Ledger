import { useFilters } from "@/store/filters";

export function FilterBar() {
  const { theme, setTheme } = useFilters();
  const cycleTheme = () =>
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  const themeIcon = theme === "light" ? "☀" : theme === "dark" ? "☾" : "◑";
  return (
    <div className="filterbar filterbar--theme">
      <button className="btn theme-toggle" onClick={cycleTheme}
        title={`Theme: ${theme}`} aria-label={`Theme: ${theme}. Change theme`}>
        <span aria-hidden>{themeIcon}</span>
      </button>
    </div>
  );
}
