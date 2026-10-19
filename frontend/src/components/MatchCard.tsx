import type { LiveMatch, SideStats } from "../types";
import { ageLabel, barWidth, marketLabel, num, pct, qualityLabel, statusLabel } from "../format";

interface Props {
  match: LiveMatch;
  onOpen: (id: string) => void;
}

const TOP_MARKETS_GOAL = ["goal_next_5_min", "goal_next_10_min", "goal_next_15_min", "goal_rest_at_least_one"];
const TOP_MARKETS_CORNER = [
  "corner_next_5_min",
  "corner_next_10_min",
  "corner_next_15_min",
  "corner_rest_at_least_one",
];

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

      <div className="probs">
        <div className={`engine ${pred.goal_sufficient ? "" : "engine--insufficient"}`}>
          <div className="engine__title">GOL {pred.goal_sufficient ? "" : "· Yetersiz veri"}</div>
          {pred.goal_sufficient ? (
            <ul className="probs__list">
              {TOP_MARKETS_GOAL.map((m) =>
                g[m] !== undefined ? (
                  <li key={m}>
                    <span className="probs__label">{marketLabel(m)}</span>
                    <span className="probs__bar">
                      <span style={{ width: barWidth(g[m]) }} />
                    </span>
                    <span className="probs__value">{pct(g[m])}</span>
                  </li>
                ) : null
              )}
            </ul>
          ) : (
            <div className="muted small">{pred.goal_insufficient_reason ?? "Yetersiz veri"}</div>
          )}
          <div className="engine__conf">Güven: {num(pred.goal_confidence, 2)}/1.0</div>
        </div>

        <div className={`engine ${pred.corner_sufficient ? "" : "engine--insufficient"}`}>
          <div className="engine__title">KORNER {pred.corner_sufficient ? "" : "· Yetersiz veri"}</div>
          {pred.corner_sufficient ? (
            <ul className="probs__list">
              {TOP_MARKETS_CORNER.map((m) =>
                c[m] !== undefined ? (
                  <li key={m}>
                    <span className="probs__label">{marketLabel(m)}</span>
                    <span className="probs__bar">
                      <span style={{ width: barWidth(c[m]) }} />
                    </span>
                    <span className="probs__value">{pct(c[m])}</span>
                  </li>
                ) : null
              )}
            </ul>
          ) : (
            <div className="muted small">{pred.corner_insufficient_reason ?? "Yetersiz veri"}</div>
          )}
          <div className="engine__conf">Güven: {num(pred.corner_confidence, 2)}/1.0</div>
        </div>
      </div>

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
