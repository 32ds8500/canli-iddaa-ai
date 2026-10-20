import { useCallback, useEffect, useState } from "react";
import { fetchDayMatches, fetchPreviews, refreshDay } from "../api";
import type { LiveMatch, PrematchPreview } from "../types";
import { MatchCard } from "./MatchCard";

interface Props {
  onOpen: (id: string) => void;
}

function todayIso(): string {
  const d = new Date();
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 10);
}

export function TodayBoard({ onOpen }: Props) {
  const [date, setDate] = useState(todayIso());
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [previews, setPreviews] = useState<Record<string, PrematchPreview>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (autoSeed = false) => {
    try {
      let res = await fetchDayMatches(date);
      if (autoSeed && res.count === 0) {
        await refreshDay(date);
        res = await fetchDayMatches(date);
      }
      setMatches(res.matches);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    setLoading(true);
    load(true);
  }, [load]);

  useEffect(() => {
    const hasUpcoming = matches.some((m) => m.status.short === "NS" || m.status.short === "TBD");
    if (!hasUpcoming) {
      setPreviews({});
      return;
    }
    let cancelled = false;
    fetchPreviews(date)
      .then((r) => {
        if (!cancelled) setPreviews(r.previews ?? {});
      })
      .catch(() => {
        /* onizleme opsiyonel */
      });
    return () => {
      cancelled = true;
    };
  }, [matches, date]);

  const doRefresh = async () => {
    setBusy(true);
    try {
      await refreshDay(date);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const live = matches.filter((m) => ["1H", "2H", "HT", "ET", "BT", "P", "LIVE", "IN_PLAY", "PAUSED", "SUSP", "INT"].includes(m.status.short));
  const others = matches.filter((m) => !live.some((x) => x.id === m.id));

  return (
    <section className="board">
      <div className="filters">
        <label className="field">
          <span>Tarih</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <button className="btn" onClick={doRefresh} disabled={busy}>
          {busy ? "Yükleniyor…" : "Günün maçlarını çek"}
        </button>
        <span className="muted small">{matches.length} maç · {live.length} canlı</span>
      </div>

      {error && <div className="errorbox">Hata: {error}</div>}
      {loading && <div className="muted pad">Yükleniyor…</div>}

      {!loading && matches.length === 0 && !error && (
        <div className="empty">
          <p>Bu tarihte hedef liglerde maç bulunamadı.</p>
          <p className="muted small">"Günün maçlarını çek" ile sağlayıcıdan günün fikstürünü indirebilirsin.</p>
        </div>
      )}

      {live.length > 0 && <h2 className="section-title">Canlı</h2>}
      <div className="board__grid">
        {live.map((m) => (
          <MatchCard key={m.id} match={m} preview={previews[m.id]} onOpen={onOpen} />
        ))}
      </div>

      {others.length > 0 && <h2 className="section-title">Diğer maçlar</h2>}
      <div className="board__grid">
        {others.map((m) => (
          <MatchCard key={m.id} match={m} preview={previews[m.id]} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}
