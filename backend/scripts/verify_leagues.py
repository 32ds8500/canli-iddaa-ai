"""Desteklenen 7 organizasyonu GERCEK API yanitindan dogrular.

Kullanim (backend dizininden):
    python scripts/verify_leagues.py

Kimlikler tahmin edilmez; /leagues yanitindaki gercek degerlerle dogrulanir
ve veritabanina yazilir. Anahtar yoksa acikca bildirir ve cikar.
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
from app.providers import TARGET_COMPETITIONS
from app.providers.api_football import ApiFootballProvider
from app.providers.base import NotConfiguredError, ProviderError

# Beklenen isim anahtar kelimeleri (gevsek eslesme)
EXPECTED_KEYWORDS: dict[str, list[str]] = {
    "super_lig": ["super lig", "süper lig"],
    "serie_a": ["serie a"],
    "la_liga": ["la liga", "primera division"],
    "ligue_1": ["ligue 1"],
    "champions_league": ["champions league"],
    "europa_league": ["europa league"],
    "conference_league": ["conference league"],
}


def main() -> int:
    settings = get_settings()
    provider = ApiFootballProvider(settings)

    if not provider.is_configured():
        print("HATA: API_FOOTBALL_KEY tanimli degil.")
        print("Gercek dogrulama icin backend/.env dosyasina anahtarinizi girin.")
        print("Ornek: cp .env.example .env  # sonra API_FOOTBALL_KEY=...")
        print("SONUC: DOGRULAMA YAPILAMADI (anahtar eksik).")
        return 2

    init_db()

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
    try:
        for comp in TARGET_COMPETITIONS:
            cid = comp["api_football_id"]
            print("=" * 70)
            print(f"{comp['name']} (beklenen API id={cid})")
            try:
                leagues = provider.get_leagues([cid])
            except ProviderError as exc:
                print(f"  HATA: istek basarisiz: {exc}")
                all_ok = False
                continue
            if not leagues:
                print("  BULUNAMADI: bu id icin organizasyon donmedi. Kimlik yanlis olabilir.")
                all_ok = False
                continue
            found_any = False
            for lg in leagues:
                name_l = lg.name.lower()
                keyword_ok = any(k in name_l for k in EXPECTED_KEYWORDS.get(comp["key"], []))
                mark = "OK" if keyword_ok else "ISIM FARKLI"
                if not keyword_ok:
                    all_ok = False
                print(f"  [{mark}] id={lg.provider_league_id} | {lg.name} | {lg.country} | tip={lg.kind} | sezon={lg.current_season}")
                stored = normalizer.upsert_league(db, lg)
                stored.coverage_notes = (
                    "Canli istatistik kapsami ancak gercek mac verisi gozlemlendiginde kesinlesir."
                )
                found_any = True
            if not found_any:
                all_ok = False
        db.commit()

        # Canli erisim testi (id listesiyle)
        print("=" * 70)
        print("Canli mac erisimi testi (bu an canli mac olmayabilir)...")
        try:
            live = provider.get_live_fixtures([c["api_football_id"] for c in TARGET_COMPETITIONS])
            print(f"  Ilgili liglerde su an canli mac sayisi: {len(live)}")
        except ProviderError as exc:
            print(f"  UYARI: canli liste alinamadi: {exc}")
    finally:
        db.close()

    print("=" * 70)
    if all_ok:
        print("SONUC: Tum 7 organizasyon gercek API yanitiyla dogrulandi ve kaydedildi.")
        return 0
    print("SONUC: Bazi organizasyonlar dogrulanamadi. Yukaridaki isaretleri inceleyin.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
