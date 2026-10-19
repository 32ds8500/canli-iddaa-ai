import { useEffect, useState } from "react";
import { fetchSystemStatus } from "../api";
import type { SystemStatus } from "../types";
import { num } from "../format";

export function StatusBar() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchSystemStatus()
        .then((s) => alive && (setStatus(s), setError(null)))
        .catch((e) => alive && setError(String(e)));
    load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (error) {
    return (
      <header className="statusbar statusbar--error">
        <div className="statusbar__title">CANLI İDDAA AI</div>
        <div className="statusbar__msg">Sunucuya ulaşılamıyor: {error}</div>
      </header>
    );
  }

  const configured = status?.provider.configured ?? false;

  return (
    <header className="statusbar">
      <div className="statusbar__row">
        <div className="statusbar__title">CANLI İDDAA AI</div>
        <div className={`pill ${configured ? "pill--ok" : "pill--warn"}`}>
          {configured ? "Sağlayıcı: bağlı" : "API anahtarı yok"}
        </div>
      </div>
      {status && (
        <div className="statusbar__meta">
          <span>
            Tahmin: <b>{num(status.counts.predictions)}</b> · Sonuçlanan:{" "}
            <b>{num(status.counts.settled_predictions)}</b> · Maç: <b>{num(status.counts.matches)}</b>
          </span>
          {status.quota && (
            <span className="statusbar__quota">
              Kota: {status.quota.daily_used}/{status.quota.daily_limit} (kalan {status.quota.daily_remaining})
            </span>
          )}
        </div>
      )}
      {status && !configured && status.provider.config_hint && (
        <div className="statusbar__hint">{status.provider.config_hint}</div>
      )}
      <div className="statusbar__disclaimer">
        Olasılıklar kesinlik veya kazanç garantisi değildir. Yetersiz veride sonuç üretilmez.
      </div>
    </header>
  );
}
