from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from doctrine_engine.engines.models import (
    EngineBar,
    PatternEngineResult,
    StructureEngineResult,
    ZoneEngineResult,
)

MarketRegime = Literal[
    "BULLISH_TREND",
    "CHOP",
    "RISK_OFF",
    "HIGH_VOL_EXPANSION",
    "WEAK_DRIFT",
]
SectorRegime = Literal["SECTOR_STRONG", "SECTOR_NEUTRAL", "SECTOR_WEAK"]


@dataclass(frozen=True, slots=True)
class RegimeIndexInput:
    ticker: Literal["SPY", "QQQ", "IWM"]
    latest_bar: EngineBar
    structure: StructureEngineResult
    zone: ZoneEngineResult
    pattern: PatternEngineResult
    structure_history: list[StructureEngineResult]


@dataclass(frozen=True, slots=True)
class SectorRegimeInput:
    sector_name: str
    sector_etf_ticker: str
    latest_bar: EngineBar
    structure: StructureEngineResult
    zone: ZoneEngineResult
    pattern: PatternEngineResult
    structure_history: list[StructureEngineResult]
    relative_strength_vs_spy: Decimal | None
    momentum_persistence_score: Decimal | None


@dataclass(frozen=True, slots=True)
class StockRelativeRegimeInput:
    symbol_id: uuid.UUID
    ticker: str
    sector_name: str
    latest_bar: EngineBar
    relative_strength_vs_spy: Decimal | None
    relative_strength_vs_sector: Decimal | None
    structure_quality_score: Decimal | None


@dataclass(frozen=True, slots=True)
class BreadthInput:
    advance_decline_ratio: Decimal | None
    up_volume_ratio: Decimal | None
    known_at: datetime


@dataclass(frozen=True, slots=True)
class VolatilityInput:
    realized_volatility_20d: Decimal | None
    realized_volatility_5d: Decimal | None
    known_at: datetime


@dataclass(frozen=True, slots=True)
class RegimeEngineInput:
    market_indexes: list[RegimeIndexInput]
    sector: SectorRegimeInput
    stock_relative: StockRelativeRegimeInput
    breadth: BreadthInput | None
    volatility: VolatilityInput | None


@dataclass(frozen=True, slots=True)
class RegimeEngineConfig:
    config_version: str = "v1"
    bearish_event_lookback_bars: int = 3
    high_vol_ratio: Decimal = Decimal("1.25")
    risk_off_vol_ratio: Decimal = Decimal("1.50")
    breadth_strong_threshold: Decimal = Decimal("1.20")
    breadth_weak_threshold: Decimal = Decimal("0.90")
    sector_rs_strong_threshold: Decimal = Decimal("0.02")
    sector_rs_weak_threshold: Decimal = Decimal("-0.02")
    momentum_supportive_threshold: Decimal = Decimal("0.60")
    momentum_hostile_threshold: Decimal = Decimal("0.40")
    weak_sector_market_permission_block_threshold: Decimal = Decimal("0.65")


@dataclass(frozen=True, slots=True)
class RegimeEngineResult:
    config_version: str
    market_regime: MarketRegime
    sector_regime: SectorRegime
    market_permission_score: Decimal
    sector_permission_score: Decimal
    stock_structure_quality_score: Decimal | None
    allows_longs: bool
    coverage_complete: bool
    reason_codes: list[str]
    known_at: datetime
    extensible_context: dict[str, Any]


__all__ = [
    "BreadthInput",
    "MarketRegime",
    "RegimeEngineConfig",
    "RegimeEngineInput",
    "RegimeEngineResult",
    "RegimeIndexInput",
    "SectorRegime",
    "SectorRegimeInput",
    "StockRelativeRegimeInput",
    "VolatilityInput",
]
