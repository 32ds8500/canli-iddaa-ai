"""Kota-dostu arka plan gorevleri (APScheduler)."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.api.deps import get_ingest_singleton, get_provider_singleton
from app.config import get_settings
from app.db import SessionLocal
from app.eval.settlement import settle_finished_matches
from app.services.odds import OddsService
from app.providers.base import NotConfiguredError, ProviderError

logger = logging.getLogger("canli-iddaa.scheduler")

# Her dongude istatistik cekilecek maksimum mac sayisi (kota korumasi)
WATCHLIST_LIMIT = 2


def refresh_live_job() -> None:
    provider = get_provider_singleton()
    if not provider.is_configured():
        logger.info("Saglayici yapilandirilmamis; canli yenileme atlandi.")
        return
    quota = getattr(provider, "_quota", None)
    if quota is not None and not quota.can_call(cost=1):
        logger.warning("Gunluk kota yetersiz; canli yenileme atlandi (ucretli plana gecis yok).")
        return
    ingest = get_ingest_singleton()
    db = SessionLocal()
    try:
        matches = ingest.refresh_live(db)
        logger.info("Canli liste yenilendi: %d mac", len(matches))
        # en guncel birkac mac icin istatistik cek (kota dostu)
        matches.sort(key=lambda m: (m.elapsed_minute or 0), reverse=True)
        for match in matches[:WATCHLIST_LIMIT]:
            if quota is not None and not quota.can_call(cost=2):
                break
            try:
                ingest.enrich_match(db, match)
            except ProviderError as exc:
                logger.warning("Istatistik cekilemedi (%s): %s", match.id, exc)
    except NotConfiguredError:
        pass
    except ProviderError as exc:
        logger.warning("Canli yenileme hatasi: %s", exc)
    finally:
        db.close()


def settle_job() -> None:
    db = SessionLocal()
    try:
        updated = settle_finished_matches(db)
        if updated:
            logger.info("Sonuclandirilan tahmin sayisi: %d", updated)
    finally:
        db.close()


def refresh_odds_job() -> None:
    service = OddsService()
    if not service.is_configured():
        return
    db = SessionLocal()
    try:
        stored = service.refresh(db)
        if stored:
            logger.info("Oranlar guncellendi: %d kayit", stored)
    finally:
        db.close()


def build_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_live_job,
        "interval",
        seconds=settings.live_poll_interval_seconds,
        id="refresh_live",
        max_instances=1,
        coalesce=True,
    )
    if settings.odds_configured:
        scheduler.add_job(
            refresh_odds_job,
            "interval",
            seconds=settings.odds_refresh_interval_seconds,
            id="refresh_odds",
            max_instances=1,
            coalesce=True,
        )
    scheduler.add_job(
        settle_job,
        "interval",
        seconds=settings.outcome_settle_interval_seconds,
        id="settle",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
