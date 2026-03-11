from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.event_risk.models import EventRiskEngineResult
from doctrine_engine.regime.models import RegimeEngineResult

RankingState = Literal["RANKED", "SKIPPED_NOT_LONG", "SKIPPED_BLOCKED"]
RankingTier = Literal["TOP", "HIGH", "MEDIUM", "LOW", "DO_NOT_QUEUE"]
RankingGrade = Literal["R1", "R2", "R3", "R4", "R0"]
RankingLabel = Literal[
    "BASELINE_TOP",
    "BASELINE_HIGH",
    "BASELINE_MEDIUM",
    "BASELINE_LOW",
    "BLOCKED_EVENT_RISK",
    "BLOCKED_NON_LONG",
]


@dataclass(frozen=True, slots=True)
class RankingEngineInput:
    signal_id: uuid.UUID
    signal_result: SignalEngineResult
    trade_plan_result: TradePlanEngineResult
    regime_result: RegimeEngineResult
    event_risk_result: EventRiskEngineResult


@dataclass(frozen=True, slots=True)
class RankingEngineConfig:
    config_version: str = "v1"
    top_threshold: Decimal = Decimal("0.85")
    high_threshold: Decimal = Decimal("0.75")
    medium_threshold: Decimal = Decimal("0.65")
    min_rr_for_positive_rank: Decimal = Decimal("1.20")
    min_risk_distance: Decimal = Decimal("0.05")
    grade_weight_a_plus: Decimal = Decimal("0.22")
    grade_weight_a: Decimal = Decimal("0.16")
    grade_weight_b: Decimal = Decimal("0.08")
    confidence_multiplier: Decimal = Decimal("0.30")
    setup_weight_recontainment: Decimal = Decimal("0.15")
    setup_weight_reclaim: Decimal = Decimal("0.12")
    setup_weight_discount: Decimal = Decimal("0.10")
    setup_weight_equilibrium: Decimal = Decimal("0.08")
    entry_weight_confirmation: Decimal = Decimal("0.08")
    entry_weight_base: Decimal = Decimal("0.05")
    entry_weight_aggressive: Decimal = Decimal("0.03")
    regime_bonus_bullish_trend: Decimal = Decimal("0.08")
    regime_bonus_weak_drift: Decimal = Decimal("0.04")
    regime_penalty_chop: Decimal = Decimal("0.04")
    regime_penalty_high_vol_expansion: Decimal = Decimal("0.08")
    sector_bonus_strong: Decimal = Decimal("0.06")
    sector_penalty_weak: Decimal = Decimal("0.05")
    market_permission_multiplier: Decimal = Decimal("0.10")
    sector_permission_multiplier: Decimal = Decimal("0.08")
    rr1_bonus_strong: Decimal = Decimal("0.10")
    rr1_bonus_positive: Decimal = Decimal("0.05")
    rr1_penalty_weak: Decimal = Decimal("0.08")
    rr2_bonus_strong: Decimal = Decimal("0.06")
    confirmation_entry_bonus: Decimal = Decimal("0.03")
    aggressive_entry_penalty: Decimal = Decimal("0.02")
    trail_structural_bonus: Decimal = Decimal("0.03")
    partial_coverage_penalty: Decimal = Decimal("0.03")


@dataclass(frozen=True, slots=True)
class RankingEngineResult:
    config_version: str
    signal_id: uuid.UUID
    symbol_id: uuid.UUID
    ticker: str
    ranking_state: RankingState
    ranking_tier: RankingTier
    ranking_grade: RankingGrade
    ranking_label: RankingLabel
    baseline_score: Decimal
    final_score: Decimal
    reason_codes: list[str]
    known_at: datetime
    extensible_context: dict[str, Any]


__all__ = [
    "RankingEngineConfig",
    "RankingEngineInput",
    "RankingEngineResult",
    "RankingGrade",
    "RankingLabel",
    "RankingState",
    "RankingTier",
]
