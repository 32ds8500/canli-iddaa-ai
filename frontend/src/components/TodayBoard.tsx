import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDayMatches, fetchMatchPreview, fetchPreviews, refreshDay } from "../api";
import type { LiveMatch, PrematchPreview } from "../types";
import { MatchCard } from "./MatchCard";

interface Props {
  onOpen: (id: string) => void;
}

const LIVE_STATUSES = ["1H", "2H", "HT", "ET", "BT", "P", "LIVE", "IN_PLAY", "PAUSED", "SUSP", "INT"];
const PREVIEW_LIMIT = 8;

function todayIso(): string {
  const d = new Date();
  const off = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - off).toISOString().slice(0, 10);
}

function isUpcoming(m: LiveMatch): boolean {
  return m.status.short === "NS" || m.status.short === "TBD";
}

export function TodayBoard({ onOpen }: Props) {
  const [date, setDate] = useState(todayIso());
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [previews, setPreviews] = useState<Record<string, PrematchPreview>>({});
  const [previewBusy, setPreviewBusy] = useState<Record<string, boolean>>({});
  const [league, setLeague] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (autoSeed = false) => {
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
    },
    [date],
  );

  useEffect(() => {
    setLoading(true);
    setLeague("");
    setQuery("");
    load(true);
  }, [load]);

  useEffect(() => {
    const upcoming = matches.filter(isUpcoming);
    if (!upcoming.length) {
      setPreviews({});
      return;
    }
    let cancelled = false;
    fetchPreviews(date, PREVIEW_LIMIT)
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

  const loadPreview = async (id: string) => {
    setPreviewBusy((b) => ({ ...b, [id]: true }));
    try {
      const r = await fetchMatchPreview(id);
      setPreviews((p) => ({ ...p, [id]: r.preview }));
    } catch {
      /* tek mac onizlemesi basarisizsa sessiz gec */
    } finally {
      setPreviewBusy((b) => ({ ...b, [id]: false }));
    }
  };

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

  const leagues = useMemo(
    () => Array.from(new Set(matches.map((m) => m.league.name ?? "Diğer"))).sort((a, b) => a.localeCompare(b, "tr")),
    [matches],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return matches.filter((m) => {
      if (league && (m.league.name ?? "Diğer") !== league) return false;
      if (!q) return true;
      return `${m.home.name ?? ""} ${m.away.name ?? ""}`.toLowerCase().includes(q);
    });
  }, [matches, league, query]);

  const live = filtered.filter((m) => LIVE_STATUSES.includes(m.status.short));
  const others = filtered.filter((m) => !LIVE_STATUSES.includes(m.status.short));

  const groups = useMemo(() => {
    const map = new Map<string, LiveMatch[]>();
    for (const m of others) {
      const key = m.league.name ?? "Diğer";
      const arr = map.get(key);
      if (arr) arr.push(m);
      else map.set(key, [m]);
    }
    return Array.from(map.entries())
      .map(([name, items]) => ({
        name,
        items: items.sort((a, b) => (a.kickoff_at ?? "").localeCompare(b.kickoff_at ?? "")),
      }))
      .sort((a, b) => (a.items[0]?.kickoff_at ?? "").localeCompare(b.items[0]?.kickoff_at ?? ""));
  }, [others]);

  return (
    <section className="board">
      <div className="filters">
        <label className="field">
          <span>Tarih</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Lig</span>
          <select value={league} onChange={(e) => setLeague(e.target.value)}>
            <option value="">Tüm ligler</option>
            {leagues.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Ara</span>
          <input
            type="search"
            placeholder="Takım adı"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button className="btn" onClick={doRefresh} disabled={busy}>
          {busy ? "Yükleniyor…" : "Günün maçlarını çek"}
        </button>
        <span className="muted small">
          {filtered.length} maç · {live.length} canlı · {leagues.length} lig
        </span>
      </div>

      {error && <div className="errorbox">Hata: {error}</div>}
      {loading && <div className="muted pad">Yükleniyor…</div>}

      {!loading && matches.length === 0 && !error && (
        <div className="empty">
          <p>Bu tarihte maç bulunamadı.</p>
          <p className="muted small">"Günün maçlarını çek" ile sağlayıcıdan günün fikstürünü indirebilirsin.</p>
        </div>
      )}

      {live.length > 0 && <h2 className="section-title">Canlı</h2>}
      <div className="board__grid">
        {live.map((m) => (
          <MatchCard
            key={m.id}
            match={m}
            preview={previews[m.id]}
            previewBusy={previewBusy[m.id]}
            onPreview={loadPreview}
            onOpen={onOpen}
          />
        ))}
      </div>

      {groups.map((g, idx) => (
        <details className="league-group" key={g.name} open={idx < 2}>
          <summary>
            <span className="league-group__name">{g.name}</span>
            <span className="muted small">{g.items.length} maç</span>
          </summary>
          <div className="board__grid">
            {g.items.map((m) => (
              <MatchCard
                key={m.id}
                match={m}
                preview={previews[m.id]}
                previewBusy={previewBusy[m.id]}
                onPreview={loadPreview}
                onOpen={onOpen}
              />
            ))}
          </div>
        </details>
      ))}
    </section>
  );
}
