"""FastAPI uygulamasi."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.routes_matches import router as matches_router
from app.api.routes_performance import router as performance_router
from app.api.routes_system import router as system_router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.ingest.live import LIVE_SHORT_STATUSES
from app.models import Match
from app.services.match_view import key_markets, serialize_match
from app.services.prediction_service import run_models
from app.services.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("canli-iddaa")

settings = get_settings()

app = FastAPI(
    title="Canli Iddaa AI",
    description=(
        "Gercek canli futbol verileriyle gol ve korner olasiligi ureten analiz sistemi. "
        "Kesin kazanc iddiasi yoktur; belirsizligi olcen bir karar destek sistemidir."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(matches_router)
app.include_router(performance_router)

_scheduler = None


@app.on_event("startup")
def _startup() -> None:
    global _scheduler
    init_db()
    if settings.enable_scheduler:
        _scheduler = build_scheduler()
        _scheduler.start()
        logger.info("Zamanlayici baslatildi.")


@app.on_event("shutdown")
def _shutdown() -> None:
    if _scheduler is not None:
        with contextlib.suppress(Exception):
            _scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "provider_configured": settings.api_football_configured}


def _live_payload() -> dict:
    db = SessionLocal()
    try:
        matches = db.execute(select(Match).where(Match.status_short.in_(list(LIVE_SHORT_STATUSES)))).scalars().all()
        items = []
        for m in matches:
            bundle = run_models(db, m)
            items.append(
                {
                    "id": m.id,
                    "minute": m.elapsed_minute,
                    "score": {"home": m.home_goals, "away": m.away_goals},
                    "data_quality": m.data_quality,
                    "goal": key_markets(bundle.goal),
                    "corner": key_markets(bundle.corner),
                    "goal_sufficient": bundle.goal.sufficient,
                    "corner_sufficient": bundle.corner.sufficient,
                }
            )
        return {"count": len(items), "matches": items}
    finally:
        db.close()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_json(_live_payload())
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await ws.close()


# --- Statik arayuz (varsa) ---
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "message": "Canli Iddaa AI API calisiyor. Arayuz icin /docs veya frontend derlemesi gerekir.",
                "docs": "/docs",
                "provider_configured": settings.api_football_configured,
            }
        )
