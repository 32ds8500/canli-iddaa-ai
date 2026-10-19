"""Motor ciktisi icin ortak veri tipleri."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketPrediction:
    market: str
    probability: float
    horizon_minutes: int | None
    threshold: float | None
    rationale: str


@dataclass
class EngineResult:
    target: str  # goal|corner
    model_name: str
    model_version: str
    predictions: list[MarketPrediction] = field(default_factory=list)
    confidence: float = 0.0
    sufficient: bool = True
    insufficient_reason: str | None = None
    factors: list[str] = field(default_factory=list)
    expected: dict[str, float] = field(default_factory=dict)
