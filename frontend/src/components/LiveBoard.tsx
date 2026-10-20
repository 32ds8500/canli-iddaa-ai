import { useCallback, useEffect, useRef, useState } from "react";
import { enrichWatchlist, fetchLiveMatches, fetchMatchPreview, refreshLive } from "../api";
import type { LiveFilters } from "../api";
import type { LiveMatch, PrematchPreview } from "../types";
import { Filters } from "./Filters";
import { MatchCard } from "./MatchCard";

interface Props {
  onOpen: (id: string) => void;
}

export function LiveBoard({ onOpen }: Props) {
  const [filters, setFilters] = useState<LiveFilters>({});
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [previews, setPreviews] = useState<Record<string, PrematchPreview>>({});
  const [previewBusy, setPreviewBusy] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

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

  const load = useCallback(async () => {
    try {
      const res = await fetchLiveMatches(filters);
      setMatches(res.matches);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    setLoading(true);
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  const autoLoaded = useRef<Set<string>>(new Set());

  useEffect(() => {
    const need = matches
      .filter((m) => !m.predictions?.goal && !previews[m.id] && !autoLoaded.current.has(m.id))
      .slice(0, 12);
    need.forEach((m) => {
      autoLoaded.current.add(m.id);
      loadPreview(m.id);
    });
  }, [matches, previews]);

  const doRefresh = async () => {
    setBusy(true);
    try {
      await refreshLive();
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const doEnrich = async () => {
    setBusy(true);
    try {
      await enrichWatchlist(3);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="board">
      <Filters filters={filters} onChange={setFilters} onRefresh={doRefresh} onEnrich={doEnrich} busy={busy} />

      {error && <div className="errorbox">Hata: {error}</div>}

      {loading && matches.length === 0 && <div className="muted pad">Yükleniyor…</div>}

      {!loading && matches.length === 0 && !error && (
        <div className="empty">
          <p>Şu anda izlenen canlı maç yok.</p>
          <p className="muted small">
            Şu anda canlı maç yok. Günün tüm maçlarını <b>Bugün</b> sekmesinden görebilirsin.
          </p>
        </div>
      )}

      <div className="board__grid">
        {matches.map((m) => (
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
    </section>
  );
}
