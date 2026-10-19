import { useEffect, useState } from "react";
import { fetchPerformance } from "../api";
import type { PerfSegment } from "../types";
import { num } from "../format";

const DIMENSIONS = [
  { value: "overall", label: "Genel" },
  { value: "target", label: "Hedef (gol/korner)" },
  { value: "league", label: "Lig" },
  { value: "minute", label: "Dakika" },
  { value: "score", label: "Skor" },
  { value: "market", label: "Piyasa" },
];

export function PerformanceView() {
  const [dimension, setDimension] = useState("overall");
  const [segments, setSegments] = useState<PerfSegment[]>([]);
  const [minSample, setMinSample] = useState(30);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchPerformance(dimension)
      .then((res) => {
        if (!alive) return;
        setSegments((res as unknown as { segments: PerfSegment[] }).segments);
        setError(null);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [dimension]);

  useEffect(() => {
    fetchPerformance("overall")
      .then((res) => {
        const r = res as unknown as { min_sample_for_percentage: number; note: string };
        setMinSample(r.min_sample_for_percentage);
        setNote(r.note);
      })
      .catch(() => undefined);
  }, []);

  return (
    <section className="perf">
      <div className="filters__row">
        <label>
          Boyut
          <select value={dimension} onChange={(e) => setDimension(e.target.value)}>
            {DIMENSIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="notice">
        Yüzde/performans yalnızca en az <b>{minSample}</b> sonuçlanmış tahmin içeren segmentlerde gösterilir. {note}
      </div>

      {error && <div className="errorbox">Hata: {error}</div>}

      {segments.length === 0 && !error && (
        <div className="empty">
          <p>Henüz sonuçlanmış tahmin yok.</p>
          <p className="muted small">
            Performans ölçümü, canlı tahminler biten maçlarla sonuçlandırıldıkça oluşur.
          </p>
        </div>
      )}

      <div className="perf__grid">
        {segments.map((s) => (
          <div className="card perfcard" key={s.key}>
            <div className="perfcard__head">
              <b>{s.label}</b>
              <span className="pill">{s.count} örnek</span>
            </div>
            {s.metrics === null ? (
              <div className="muted small">{s.note ?? "Yetersiz örnek — yüzde gösterilmez."}</div>
            ) : (
              <table className="metrics">
                <tbody>
                  <tr>
                    <td>Brier</td>
                    <td>{num(s.metrics.brier, 4)}</td>
                    <td className="muted">temel: {num(s.metrics.baseline_brier, 4)}</td>
                  </tr>
                  <tr>
                    <td>LogLoss</td>
                    <td>{num(s.metrics.log_loss, 4)}</td>
                    <td className="muted">temel: {num(s.metrics.baseline_log_loss, 4)}</td>
                  </tr>
                  <tr>
                    <td>Gerçekleşme</td>
                    <td>{num(s.metrics.base_rate * 100, 1)}%</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            )}
            {s.metrics && s.metrics.calibration.length > 0 && (
              <div className="calib">
                <div className="calib__title muted small">Kalibrasyon</div>
                {s.metrics.calibration.map((b, i) => (
                  <div className="calib__row" key={i}>
                    <span className="muted small">
                      %{num(b.low * 100)}–%{num(b.high * 100)}
                    </span>
                    <span className="calib__bar">
                      <span style={{ width: `${Math.min(100, b.avg_predicted * 100)}%` }} className="pred" />
                      <span style={{ width: `${Math.min(100, b.actual_rate * 100)}%` }} className="actual" />
                    </span>
                    <span className="muted small">
                      tahmin {num(b.avg_predicted * 100, 1)}% / gerçek {num(b.actual_rate * 100, 1)}% ({b.count})
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
