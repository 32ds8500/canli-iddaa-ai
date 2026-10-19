import type { LiveFilters } from "../api";

interface Props {
  filters: LiveFilters;
  onChange: (next: LiveFilters) => void;
  onRefresh: () => void;
  onEnrich: () => void;
  busy: boolean;
}

const QUALITIES = [
  { value: "", label: "Tüm kaliteler" },
  { value: "good", label: "İyi" },
  { value: "partial", label: "Kısmi" },
  { value: "conflicting", label: "Çelişkili" },
  { value: "missing", label: "Eksik" },
];

export function Filters({ filters, onChange, onRefresh, onEnrich, busy }: Props) {
  const set = (patch: Partial<LiveFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="filters">
      <div className="filters__row">
        <label>
          Min. dakika
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={130}
            value={filters.minute_min ?? ""}
            onChange={(e) => set({ minute_min: e.target.value === "" ? undefined : Number(e.target.value) })}
          />
        </label>
        <label>
          Maks. dakika
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={130}
            value={filters.minute_max ?? ""}
            onChange={(e) => set({ minute_max: e.target.value === "" ? undefined : Number(e.target.value) })}
          />
        </label>
        <label>
          Veri kalitesi
          <select value={filters.data_quality ?? ""} onChange={(e) => set({ data_quality: e.target.value })}>
            {QUALITIES.map((q) => (
              <option key={q.value} value={q.value}>
                {q.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="filters__row">
        <label>
          Min. 10dk gol
          <input
            type="number"
            inputMode="decimal"
            step={0.05}
            min={0}
            max={1}
            value={filters.min_goal_prob ?? ""}
            onChange={(e) => set({ min_goal_prob: e.target.value === "" ? undefined : Number(e.target.value) })}
          />
        </label>
        <label>
          Min. 10dk korner
          <input
            type="number"
            inputMode="decimal"
            step={0.05}
            min={0}
            max={1}
            value={filters.min_corner_prob ?? ""}
            onChange={(e) => set({ min_corner_prob: e.target.value === "" ? undefined : Number(e.target.value) })}
          />
        </label>
        <div className="filters__actions">
          <button onClick={onRefresh} disabled={busy}>
            Canlıyı yenile
          </button>
          <button className="ghost" onClick={onEnrich} disabled={busy}>
            İstatistik çek
          </button>
        </div>
      </div>
    </div>
  );
}
