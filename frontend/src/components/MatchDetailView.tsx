import { useCallback, useEffect, useState } from "react";
import { fetchMatchDetail, refreshMatch, refreshOdds } from "../api";
import type { EngineView, MatchDetail, OddsItem } from "../types";
import { ageLabel, barWidth, marketLabel, pct, qualityLabel, statusLabel } from "../format";

interface Props {
  matchId: string;
  onBack: () => void;
}

function EnginePanel({ view }: { view: EngineView }) {
  return (
    <div className={`engine ${view.sufficient ? "" : "engine--insufficient"}`}>
      <div className="engine__title">
        {view.target === "goal" ? "GOL" : "KORNER"} · {view.model.name} v{view.model.version}
      </div>
      {view.sufficient ? (
        <ul className="probs__list">
          {view.predictions
            .filter((p) => p.horizon_minutes !== null || p.market.endsWith("at_least_one"))
            .map((p, i) => (
              <li key={`${p.market}-${i}`}>
                <span className="probs__label" title={p.rationale}>
                  {marketLabel(p.market)}
                </span>
                <span className="probs__bar">
                  <span style={{ width: barWidth(p.probability) }} />
                </span>
                <span className="probs__value">{pct(p.probability)}</span>
              </li>
            ))}
        </ul>
      ) : (
        <div className="muted small">{view.insufficient_reason ?? "Yetersiz veri"}</div>
      )}
      <div className="engine__conf">Güven: {view.confidence.toFixed(2)}/1.0</div>
      {view.factors.length > 0 && (
        <ul className="factors">
          {view.factors.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}


function modelProb(market: string, goal: Record<string, number>): number | null {
  const totals = market.match(/^totals_([\d.]+)_(over|under)$/);
  if (totals) {
    const key = `goals_total_over_${totals[1].replace(".", "_")}`;
    const over = goal[key];
    if (over === undefined) return null;
    return totals[2] === "over" ? over : 1 - over;
  }
  return null;
}

function oddsLabel(market: string, selection: string): string {
  if (market === "h2h") {
    if (selection === "home") return "Ev sahibi";
    if (selection === "draw") return "Beraberlik";
    return "Deplasman";
  }
  const totals = market.match(/^totals_([\d.]+)_(over|under)$/);
  if (totals) return `${totals[1]} ${totals[2] === "over" ? "Üst" : "Alt"}`;
  return market;
}

function OddsPanel({ detail }: { detail: MatchDetail }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const goalMap: Record<string, number> = {};
  detail.current_predictions.goal.predictions.forEach((p) => {
    goalMap[p.market] = p.probability;
  });
  const best = new Map<string, OddsItem>();
  (detail.odds ?? []).forEach((o) => {
    const key = `${o.market}|${o.selection}`;
    const prev = best.get(key);
    if (!prev || o.price > prev.price) best.set(key, o);
  });

  const rows = Array.from(best.values()).filter((o) => o.market.startsWith("totals_") || o.market === "h2h");

  const doRefresh = async () => {
    setBusy(true);
    try {
      await refreshOdds();
      setNote("Oranlar güncellendi.");
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="oddsbox">
      <div className="oddsbox__head">
        <h3>Oranlar</h3>
        <button className="ghost" onClick={doRefresh} disabled={busy}>
          {busy ? "Çekiliyor…" : "Oranları güncelle"}
        </button>
      </div>

      {rows.length === 0 ? (
        <div className="muted small">
          Bağlı oran kaynağı yok. Sunucuda <code>ODDS_API_KEY</code> tanımlanınca gerçek oranlar ve
          modelo göre değer (value) burada görünür. Oran uydurulmaz.
        </div>
      ) : (
        <table className="statstable">
          <thead>
            <tr>
              <th>Seçim</th>
              <th>Oran</th>
              <th>İma edilen</th>
              <th>Model</th>
              <th>Değer</th>
              <th>Kaynak</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => {
              const mp = modelProb(o.market, goalMap);
              const implied = o.implied_probability ?? 1 / o.price;
              const value = mp === null ? null : mp - implied;
              return (
                <tr key={`${o.market}-${o.selection}-${o.bookmaker}`}>
                  <td>{oddsLabel(o.market, o.selection)}</td>
                  <td>{o.price.toFixed(2)}</td>
                  <td>{pct(implied)}</td>
                  <td>{mp === null ? "—" : pct(mp)}</td>
                  <td className={value !== null && value > 0 ? "pos" : undefined}>
                    {value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`}
                  </td>
                  <td className="muted small">{o.bookmaker ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {note && <div className="muted small">{note}</div>}
      <div className="muted small">
        Değer = model olasılığı − oranın ima ettiği olasılık. Pozitif değer garanti değildir; marj ve
        model hatası dikkate alınmalıdır.
      </div>
    </section>
  );
}

export function MatchDetailView({ matchId, onBack }: Props) {
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const d = await fetchMatchDetail(matchId);
      setDetail(d);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  const doRefresh = async () => {
    setBusy(true);
    try {
      await refreshMatch(matchId);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="muted pad">Yükleniyor…</div>;
  if (!detail) return <div className="errorbox">Hata: {error ?? "Kayıt yok"}</div>;

  const q = qualityLabel(detail.data_quality);
  const home = detail.home.name ?? detail.home.id;
  const away = detail.away.name ?? detail.away.id;

  return (
    <section className="detail">
      <div className="detail__topbar">
        <button className="ghost" onClick={onBack}>
          ← Geri
        </button>
        <button onClick={doRefresh} disabled={busy}>
          {busy ? "Güncelleniyor…" : "Bu maçı güncelle"}
        </button>
      </div>

      <div className="detail__head">
        <div className="muted small">{detail.league.name ?? "—"}</div>
        <h2 className="detail__scoreline">
          {home} <span>{detail.score.home ?? 0} - {detail.score.away ?? 0}</span> {away}
        </h2>
        <div className="detail__meta">
          <span className="pill pill--minute">
            {statusLabel(detail.status.short)} {detail.minute != null ? `${detail.minute}'` : ""}
          </span>
          <span className={`pill ${q.cls}`}>Veri: {q.text}</span>
          <span className="muted small">Yaş: {ageLabel(detail.data_age_seconds)}</span>
        </div>
      </div>

      {error && <div className="errorbox">Hata: {error}</div>}

      <div className="detail__panels">
        <EnginePanel view={detail.current_predictions.goal} />
        <EnginePanel view={detail.current_predictions.corner} />
      </div>

      <OddsPanel detail={detail} />

      <div className="detail__baseline muted small">
        Temel oran kaynağı: {detail.current_predictions.baseline.source} · örnek maç:{" "}
        {detail.current_predictions.baseline.sample_matches}
        {detail.current_predictions.baseline.note ? ` · ${detail.current_predictions.baseline.note}` : ""}
      </div>

      <h3>İstatistikler</h3>
      <table className="statstable">
        <thead>
          <tr>
            <th>Ölçüt</th>
            <th>{home}</th>
            <th>{away}</th>
          </tr>
        </thead>
        <tbody>
          {[
            ["Şut", "shots_total"],
            ["İsabetli şut", "shots_on"],
            ["Korner", "corners"],
            ["Tehlikeli atak", "dangerous_attacks"],
            ["Topla oynama", "possession"],
            ["Sarı kart", "yellow_cards"],
            ["Kırmızı kart", "red_cards"],
          ].map(([label, key]) => (
            <tr key={key}>
              <td>{label}</td>
              <td>{valueOf(detail.stats.home, key)}</td>
              <td>{valueOf(detail.stats.away, key)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Olaylar</h3>
      {detail.events.length === 0 ? (
        <div className="muted small">Kayıtlı olay yok.</div>
      ) : (
        <ul className="events">
          {detail.events.map((e, i) => (
            <li key={i}>
              <span className="events__min">{e.minute ?? "—"}'</span>
              <span className="events__type">{e.type ?? "olay"}</span>
              <span className="muted">{e.detail ?? ""}</span>
              {e.player && <span className="muted"> · {e.player}</span>}
            </li>
          ))}
        </ul>
      )}

      <h3>Tahmin geçmişi ({detail.prediction_history.length})</h3>
      {detail.prediction_history.length === 0 ? (
        <div className="muted small">
          Bu maç için henüz kayıtlı tahmin yok. "Bu maçı güncelle" ile tahmin üretin.
        </div>
      ) : (
        <table className="histtable">
          <thead>
            <tr>
              <th>Dk</th>
              <th>Skor</th>
              <th>Piyasa</th>
              <th>Olasılık</th>
              <th>Güven</th>
              <th>Kalite</th>
              <th>Sonuç</th>
            </tr>
          </thead>
          <tbody>
            {detail.prediction_history.map((h) => (
              <tr key={h.id}>
                <td>{h.minute ?? "—"}'</td>
                <td>
                  {h.score.home ?? 0}-{h.score.away ?? 0}
                </td>
                <td title={h.rationale ?? ""}>
                  <span className="tag">{h.target === "goal" ? "G" : "K"}</span> {marketLabel(h.market)}
                </td>
                <td>{pct(h.probability)}</td>
                <td>{h.confidence != null ? h.confidence.toFixed(2) : "—"}</td>
                <td>{qualityLabel(h.data_quality).text}</td>
                <td>
                  {h.outcome?.actual == null
                    ? "bekliyor"
                    : h.outcome.actual > 0
                    ? "oldu"
                    : "olmadi"}{" "}
                  {h.outcome?.detail ? <span className="muted small">({h.outcome.detail})</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function valueOf(side: MatchDetail["stats"]["home"], key: string): string {
  if (!side) return "—";
  const v = (side as unknown as Record<string, number | null>)[key];
  return v === null || v === undefined ? "—" : String(v);
}
