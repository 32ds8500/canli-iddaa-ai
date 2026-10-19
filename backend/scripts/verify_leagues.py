"""Desteklenen 7 organizasyonu GERCEK API yanitindan dogrular.

Kullanim (backend dizininden):
    python scripts/verify_leagues.py

Kimlikler tahmin edilmez; saglayicinin gercek yanitindaki degerlerle
dogrulanir ve veritabanina yazilir. Saglayici secimi PROVIDER_MODE ile yapilir:
- auto (varsayilan): API-Football anahtari varsa o, yoksa FotMob
- fotmob: anahtarsiz, herkese acik veri
- api-football: anahtar zorunlu
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.ingest.normalizer import Normalizer
from app.providers import TARGET_COMPETITIONS, TARGET_LEAGUE_IDS, get_provider
from app.providers.base import NotConfiguredError, ProviderError
from app.providers.fotmob import FOTMOB_LEAGUE_IDS

# Beklenen isim anahtar kelimeleri (gevsek eslesme)
EXPECTED_KEYWORDS: dict[str, list[str]] = {
    "super_lig": ["super lig", "süper lig"],
    "serie_a": ["serie a"],
    "la_liga": ["la liga", "primera division"],
    "ligue_1": ["ligue 1"],
    "champions_league": ["champions league", "sampiyonlar ligi", "şampiyonlar ligi"],
    "europa_league": ["europa league", "avrupa ligi"],
    "conference_league": ["conference league", "konferans ligi"],
}


def main() -> int:
    settings = get_settings()
    provider = get_provider(settings)

    if not provider.is_configured():
        print("HATA: Saglayici yapilandirilmamis.")
        print("Gercek dogrulama icin backend/.env dosyasina API_FOOTBALL_KEY girin")
        print("veya anahtarsiz FotMob icin PROVIDER_MODE=fotmob ayarlayin.")
        print("SONUC: DOGRULAMA YAPILAMADI (saglayici yok).")
        return 2

    print(f"Saglayici: {provider.name} (mod={settings.provider_mode})")
    init_db()

    if provider.name == "api-football":
        try:
            status = provider.get_status()
            sub = status.get("response", {}).get("subscription", {})
            req = status.get("response", {}).get("requests", {})
            print(f"Saglayici plan: {sub.get('plan')} | aktif={sub.get('active')}")
            print(f"Kota: kullanilan={req.get('current')} / gunluk_limit={req.get('limit_day')}")
        except ProviderError as exc:
            print(f"UYARI: /status alinamadi: {exc}")

    all_ok = True
    db = SessionLocal()
    normalizer = Normalizer(provider.name)
    target_ids = provider.map_target_league_ids(TARGET_LEAGUE_IDS)
    try:
        for comp, provider_id in zip(TARGET_COMPETITIONS, target_ids):
            print("=" * 70)
            print(f"{comp['name']} (saglayici id={provider_id})")
            try:
                leagues = provider.get_leagues([provider_id])
            except ProviderError as exc:
                print(f"  HATA: istek basarisiz: {exc}")
                all_ok = False
                continue
            if not leagues:
                print("  BULUNAMADI: bu id icin organizasyon donmedi. Kimlik yanlis olabilir.")
                all_ok = False
                continue
            for lg in leagues:
                name_l = lg.name.lower()
                keyword_ok = any(k in name_l for k in EXPECTED_KEYWORDS.get(comp["key"], []))
                mark = "OK" if keyword_ok else "ISIM FARKLI"
                if not keyword_ok:
                    all_ok = False
                print(
                    f"  [{mark}] id={lg.provider_league_id} | {lg.name} | {lg.country} | "
                    f"tip={lg.kind} | sezon={lg.current_season}"
                )
                stored = normalizer.upsert_league(db, lg)
                stored.coverage_notes = (
                    f"{provider.name}: canli istatistik kapsami gercek mac verisiyle dogrulanir."
                )
        db.commit()

        print("=" * 70)
        print("Canli mac erisimi testi (bu an canli mac olmayabilir)...")
        try:
            live = provider.get_live_fixtures()
            print(f"  Ilgili liglerde su an canli mac sayisi: {len(live)}")
            for fx in live[:5]:
                print(f"   - {fx.league_name}: {fx.home.name} {fx.home_goals}-{fx.away_goals} {fx.away.name} ({fx.status_short})")
        except ProviderError as exc:
            print(f"  UYARI: canli liste alinamadi: {exc}")
    finally:
        db.close()

    print("=" * 70)
    if all_ok:
        print(f"SONUC: Tum 7 organizasyon {provider.name} uzerinden dogrulandi ve kaydedildi.")
        return 0
    print("SONUC: Bazi organizasyonlar dogrulanamadi. Yukaridaki isaretleri inceleyin.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
