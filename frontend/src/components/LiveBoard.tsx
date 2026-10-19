import { useCallback, useEffect, useState } from "react";
import { enrichWatchlist, fetchLiveMatches, refreshLive } from "../api";
import type { LiveFilters } from "../api";
import type { LiveMatch } from "../types";
import { Filters } from "./Filters";
import { MatchCard } from "./MatchCard";

interface Props {
  onOpen: (id: string) => void;
}

export function LiveBoard({ onOpen }: Props) {
  const [filters, setFilters] = useState<LiveFilters>({});
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

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
            Şu anda hedef liglerde oynanan maç yok. Günün tüm maçlarını <b>Bugün</b> sekmesinden görebilirsin.
          </p>
        </div>
      )}

      <div className="board__grid">
        {matches.map((m) => (
          <MatchCard key={m.id} match={m} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}
