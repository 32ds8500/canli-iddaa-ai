"""ORM modelleri (SQLAlchemy 2.0 stili).

Ilke: saglayicidan gelen her sey oldugu gibi saklanir; olmayan istatistik
"mevcut degil" (None) olarak tutulur, asla uydurulmaz.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_league_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="league")  # league|cup
    current_season: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Veri kapsami (saglayicidan dogrulanir) ---
    cov_live_stats: Mapped[bool] = mapped_column(Boolean, default=False)
    cov_corners: Mapped[bool] = mapped_column(Boolean, default=False)
    cov_dangerous_attacks: Mapped[bool] = mapped_column(Boolean, default=False)
    cov_xg: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_team_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_fixture_id: Mapped[str] = mapped_column(String(32), index=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), index=True)
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))

    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status_short: Mapped[str] = mapped_column(String(8), default="NS")
    status_long: Mapped[str | None] = mapped_column(String(64), nullable=True)
    elapsed_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)

    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_quality: Mapped[str] = mapped_column(String(16), default="unknown")
    data_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    league: Mapped[League] = relationship()
    stats: Mapped[list["MatchStat"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    events: Mapped[list["MatchEvent"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class MatchStat(Base):
    __tablename__ = "match_stats"
    __table_args__ = (UniqueConstraint("match_id", "side", "period", name="uq_match_side_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))  # home|away
    period: Mapped[str] = mapped_column(String(16), default="live")

    shots_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_off: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_blocked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dangerous_attacks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    possession: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xg: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    match: Mapped[Match] = relationship(back_populates="stats")


class StatSnapshot(Base):
    """Mac icindeki kumulatif istatistik anlik goruntusu.

    Kayan pencere (son 5/10/15 dk) hesaplari bu tablodan turetilir.
    """

    __tablename__ = "stat_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    minute: Mapped[int] = mapped_column(Integer, default=0)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    shots_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dangerous_attacks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    possession: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xg: Mapped[float | None] = mapped_column(Float, nullable=True)


class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(48), nullable=True)
    side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    player: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assist: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    match: Mapped[Match] = relationship(back_populates="events")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    minute_at_prediction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_home: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_away: Mapped[int | None] = mapped_column(Integer, nullable=True)

    target: Mapped[str] = mapped_column(String(16))  # goal|corner
    market: Mapped[str] = mapped_column(String(64), index=True)
    horizon_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    probability: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(48))
    model_version: Mapped[str] = mapped_column(String(24))

    data_quality: Mapped[str] = mapped_column(String(16), default="unknown")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    outcome: Mapped["PredictionOutcome | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actual: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1|0
    actual_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_status: Mapped[str] = mapped_column(String(16), default="pending")

    prediction: Mapped[Prediction] = relationship(back_populates="outcome")


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), index=True)
    bookmaker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market: Mapped[str] = mapped_column(String(64))
    selection: Mapped[str] = mapped_column(String(64))
    price: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    endpoint: Mapped[str] = mapped_column(String(96))
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
