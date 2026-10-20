import type { LiveMatch, PrematchPreview, SideStats } from "../types";
import { ageLabel, barWidth, kickoffLabel, marketLabel, num, pct, qualityLabel, statusLabel } from "../format";

interface Props {
  match: LiveMatch;
  preview?: PrematchPreview;
  onOpen: (id: string) => void;
}

function SideStatsLine({ label, s }: { label: string; s: SideStats | null }) {
  if (!s) {
    return (
      <div className="statsline">
        <span className="statsline__side">{label}</span>
        <span className="muted">istatistik yok</span>
      </div>
    );
  }
  return (
    <div className="statsline">
      <span className="statsline__side">{label}</span>
      <span title="Şut / isabetli">Şut {num(s.shots_total)}/{num(s.shots_on)}</span>
      <span title="Korner">Korner {num(s.corners)}</span>
      <span title="Tehlikeli atak">Teh. atak {num(s.dangerous_attacks)}</span>
      <span title="Topla oynama">%{num(s.possession)}</span>
    </div>
  );
}

function Chip({ label, value }: { label: string; value: number | undefined }) {
  if (value === undefined) return null;
  return (
    <span className="mchip" title={`${label}: ${pct(value)}`}>
      <span className="mchip__label">{label}</span>
      <span className="mchip__value">{pct(value)}</span>
    </span>
  );
}

function FormChips({ form }: { form: string[] }) {
  return (
    <span className="formchips">
      {form.slice(0, 5).map((r, i) => (
        <span key={i} className={`formchip formchip--${r.toLowerCase()}`}>
          {r === "W" ? "G" : r === "D" ? "B" : "M"}
        </span>
      ))}
    </span>
  );
}

function PrematchBlock({ preview }: { preview?: PrematchPreview }) {
  if (!preview) {
    return <div className="muted small pad-x">Maç öncesi önizleme yükleniyor…</div>;
  }
  const p = preview.prediction;
  const h = preview.home;
  const a = preview.away;
  const h2h = preview.h2h;
  const last = h2h.matches[0];
  return (
    <div className="prebox">
      <div className="mgroup__title">Maç öncesi tahmin</div>
      {p ? (
        <>
          <div className="prebar">
            <span className="prebar__seg prebar__seg--1" style={{ width: `${p.markets.home_win * 100}%` }}>
              1 {pct(p.markets.home_win)}
            </span>
            <span className="prebar__seg prebar__seg--x" style={{ width: `${p.markets.draw * 100}%` }}>
              X {pct(p.markets.draw)}
            </span>
            <span className="prebar__seg prebar__seg--2" style={{ width: `${p.markets.away_win * 100}%` }}>
              2 {pct(p.markets.away_win)}
            </span>
          </div>
          <div className="mchips">
            <Chip label="2.5 Üst" value={p.markets.over_2_5} />
            <Chip label="KG" value={p.markets.btts} />
            <Chip label="1X" value={p.markets.dc_1x} />
            <Chip label="X2" value={p.markets.dc_x2} />
            <Chip label="3.5 Üst" value={p.markets.over_3_5} />
          </div>
          <div className="muted small">
            Beklenen gol: {p.lambda_home} - {p.lambda_away}
          </div>
        </>
      ) : (
        <div className="muted small">Bu maç için yeterli geçmiş veri yok.</div>
      )}
      <div className="preform">
        <div className="preform__row">
          <span className="preform__team">{h.name}</span>
          <FormChips form={h.form} />
          <span className="muted small">
            Son {h.played}: {h.wins}G {h.draws}B {h.losses}M · {h.gf}-{h.ga}
          </span>
        </div>
        <div className="preform__row">
          <span className="preform__team">{a.name}</span>
          <FormChips form={a.form} />
          <span className="muted small">
            Son {a.played}: {a.wins}G {a.draws}B {a.losses}M · {a.gf}-{a.ga}
          </span>
        </div>
      </div>
      {h2h.played > 0 && (
        <div className="preh2h muted small">
          Aralarında son {h2h.played} ({h.name} bakışıyla): {h2h.wins}G {h2h.draws}B {h2h.losses}M
          {last ? ` · Son: ${last.home} ${last.score} ${last.away}` : ""}
        </div>
      )}
      {p && <div className="muted small">{p.note}</div>}
    </div>
  );
}

export function MatchCard({ match, preview, onOpen }: Props) {
  const q = qualityLabel(match.data_quality);
  const isUpcoming = match.status.short === "NS" || match.status.short === "TBD";
  const pred = match.predictions;
  const g = pred.goal;
  const c = pred.corner;

  return (
    <article className="card" onClick={() => onOpen(match.id)}>
      <div className="card__head">
        <div className="card__league">
          {match.league.name ?? "Bilinmeyen lig"}
          <span className="muted"> · {match.league.country ?? "—"}</span>
        </div>
        <div className="card__state">
          <span className="pill pill--minute">
            {statusLabel(match.status.short)} {match.minute != null ? `${match.minute}'` : ""}
          </span>
          <span className={`pill ${q.cls}`}>{q.text}</span>
        </div>
      </div>

      <div className="card__score">
        <span className="card__team">{match.home.name ?? match.home.id}</span>
        <span className="card__goals">
          {num(match.score.home)} - {num(match.score.away)}
        </span>
        <span className="card__team card__team--right">{match.away.name ?? match.away.id}</span>
      </div>

      <div className="card__stale muted">
        Başlama: {kickoffLabel(match.kickoff_at)} · Güncelleme yaşı: {ageLabel(match.data_age_seconds)}
      </div>

      {isUpcoming && <PrematchBlock preview={preview} />}

      {!isUpcoming && (
        <>
      {pred.source === "history" && (
        <div className="muted small pad-x">
          Maç bitti · {pred.as_of_minute != null ? `${pred.as_of_minute}. dakikada` : "maç sırasında"} kaydedilen tahminler
        </div>
      )}

      <div className="headline">
        <div className={`hl ${pred.goal_sufficient ? "" : "hl--off"}`}>
          <div className="hl__label">10 dk içinde gol</div>
          <div className="hl__value">{pred.goal_sufficient ? pct(g["goal_next_10_min"]) : "—"}</div>
          <div className="hl__bar">
            <span style={{ width: pred.goal_sufficient ? barWidth(g["goal_next_10_min"]) : "0%" }} />
          </div>
        </div>
        <div className={`hl ${pred.corner_sufficient ? "" : "hl--off"}`}>
          <div className="hl__label">10 dk içinde korner</div>
          <div className="hl__value">{pred.corner_sufficient ? pct(c["corner_next_10_min"]) : "—"}</div>
          <div className="hl__bar">
            <span style={{ width: pred.corner_sufficient ? barWidth(c["corner_next_10_min"]) : "0%" }} />
          </div>
        </div>
      </div>

      {!pred.goal_sufficient && !pred.corner_sufficient && (
        <div className="muted small pad-x">
          {pred.goal_insufficient_reason ?? pred.corner_insufficient_reason ?? "Yetersiz veri"}
        </div>
      )}

      {pred.goal_sufficient && (
        <div className="mgroup">
          <div className="mgroup__title">Gol marketleri</div>
          <div className="mchips">
            <Chip label="Sonraki 5 dk" value={g["goal_next_5_min"]} />
            <Chip label="Sonraki 15 dk" value={g["goal_next_15_min"]} />
            <Chip label="Kalan sürede gol" value={g["goal_rest_at_least_one"]} />
            <Chip label={marketLabel("goals_total_over_2_5")} value={g["goals_total_over_2_5"]} />
            <Chip label={marketLabel("goals_total_over_3_5")} value={g["goals_total_over_3_5"]} />
            <Chip label={marketLabel("goal_btts")} value={g["goal_btts"]} />
            <Chip label={marketLabel("goal_next_home")} value={g["goal_next_home"]} />
            <Chip label={marketLabel("goal_next_away")} value={g["goal_next_away"]} />
          </div>
        </div>
      )}

      {pred.corner_sufficient && (
        <div className="mgroup">
          <div className="mgroup__title">Korner marketleri</div>
          <div className="mchips">
            <Chip label="Sonraki 5 dk" value={c["corner_next_5_min"]} />
            <Chip label="Sonraki 15 dk" value={c["corner_next_15_min"]} />
            <Chip label="Kalan sürede korner" value={c["corner_rest_at_least_one"]} />
            <Chip label={marketLabel("corners_total_over_9_5")} value={c["corners_total_over_9_5"]} />
            <Chip label={marketLabel("corners_total_over_10_5")} value={c["corners_total_over_10_5"]} />
            <Chip label={marketLabel("corner_next_home")} value={c["corner_next_home"]} />
            <Chip label={marketLabel("corner_next_away")} value={c["corner_next_away"]} />
          </div>
        </div>
      )}

      <div className="card__stats">
        <SideStatsLine label={match.home.name ?? "Ev"} s={match.stats.home} />
        <SideStatsLine label={match.away.name ?? "Dep."} s={match.stats.away} />
      </div>

      <div className="card__baseline muted small">
        Temel oran kaynağı: {pred.baseline.goal_source} · örnek maç: {pred.baseline.sample_matches}
        {pred.baseline.note ? ` · ${pred.baseline.note}` : ""}
      </div>
        </>
      )}
    </article>
  );
}
