import type { LiveMatch, SideStats } from "../types";
import { ageLabel, barWidth, marketLabel, num, pct, qualityLabel, statusLabel } from "../format";

interface Props {
  match: LiveMatch;
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

export function MatchCard({ match, onOpen }: Props) {
  const q = qualityLabel(match.data_quality);
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

      <div className="card__stale muted">Güncelleme yaşı: {ageLabel(match.data_age_seconds)}</div>

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
    </article>
  );
}
