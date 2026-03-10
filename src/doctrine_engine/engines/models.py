from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from doctrine_engine.db.types import Timeframe

StructureEventType = Literal["BULLISH_BOS", "BEARISH_BOS", "BULLISH_CHOCH", "BEARISH_CHOCH"]
PatternEventType = Literal[
    "BULLISH_DISPLACEMENT",
    "BULLISH_RECLAIM",
    "BULLISH_FAKE_BREAKDOWN",
    "BULLISH_TRAP_REVERSE",
    "RECONTAINMENT_ENTERED",
    "RECONTAINMENT_INVALIDATED",
]
SwingKind = Literal["HIGH", "LOW"]
RangeSelection = Literal["BOS_ANCHORED", "BRACKETING_PAIR", "LATEST_PAIR_FALLBACK", "NO_VALID_RANGE"]
TrendState = Literal["BULLISH_SEQUENCE", "BEARISH_SEQUENCE", "MIXED", "UNDEFINED"]
RangeStatus = Literal["RANGE_AVAILABLE", "NO_VALID_RANGE"]
ZoneLocation = Literal["DISCOUNT", "EQUILIBRIUM", "PREMIUM", "NO_VALID_RANGE"]
CompressionStatus = Literal["COMPRESSED", "NOT_COMPRESSED"]
CompressionCriterion = Literal[
    "RANGE_VS_ATR",
    "LEG_CONTRACTION",
    "REALIZED_RANGE_VS_ATR",
    "NEAR_EQUILIBRIUM",
]
DisplacementStatus = Literal["NONE", "NEW_EVENT", "ACTIVE"]
DisplacementMode = Literal["SINGLE_BAR", "SEQUENCE"]
LifecycleStatus = Literal["NONE", "CANDIDATE", "NEW_EVENT", "ACTIVE", "INVALIDATED"]
TrapReverseStatus = Literal["NONE", "NEW_EVENT", "ACTIVE", "INVALIDATED"]
RecontainmentStatus = Literal["NONE", "CANDIDATE", "ACTIVE", "INVALIDATED"]
TrapReverseTrigger = Literal["BULLISH_CHOCH", "BULLISH_BOS"]
ActiveFlag = Literal[
    "COMPRESSION",
    "BULLISH_DISPLACEMENT",
    "BULLISH_RECLAIM",
    "BULLISH_FAKE_BREAKDOWN",
    "BULLISH_TRAP_REVERSE",
    "RECONTAINMENT_CANDIDATE",
    "RECONTAINMENT_ACTIVE",
]
SignalBias = Literal["BULLISH", "NEUTRAL", "BEARISH"]
InternalMTFSetupState = Literal[
    "RECONTAINMENT_CANDIDATE",
    "BULLISH_RECLAIM",
    "DISCOUNT_RESPONSE",
    "EQUILIBRIUM_HOLD",
    "INVALIDATED",
    "EXTENDED_PREMIUM",
    "CHOP",
    "NO_STRUCTURE",
]
OutputSetupState = Literal[
    "RECONTAINMENT_CONFIRMED",
    "DISCOUNT_RESPONSE",
    "EQUILIBRIUM_HOLD",
    "BULLISH_RECLAIM",
    "NO_VALID_LONG_STRUCTURE",
    "INVALIDATED",
    "EXTENDED_PREMIUM",
    "CHOP",
]
LTFTriggerState = Literal[
    "TRAP_REVERSE_BULLISH",
    "FAKE_BREAKDOWN_REVERSAL",
    "LTF_BULLISH_RECLAIM",
    "LTF_BULLISH_CHOCH",
    "LTF_BULLISH_BOS",
    "LTF_NO_TRIGGER",
]
SignalResultValue = Literal["LONG", "NONE"]
SignalResultGrade = Literal["A+", "A", "B", "IGNORE"]
SectorStrength = Literal["STRONG", "NEUTRAL", "WEAK", "UNKNOWN"]
TradePlanEntryType = Literal["AGGRESSIVE", "BASE", "CONFIRMATION"]
TradePlanTrailMode = Literal["STRUCTURAL", "NONE"]


@dataclass(frozen=True, slots=True)
class EngineBar:
    symbol_id: uuid.UUID
    timeframe: Timeframe
    bar_timestamp: datetime
    known_at: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int = 0


@dataclass(frozen=True, slots=True)
class SwingPoint:
    kind: SwingKind
    pivot_timestamp: datetime
    confirmed_at: datetime
    price: Decimal
    sequence_index: int


@dataclass(frozen=True, slots=True)
class StructureReferenceLevels:
    bullish_bos_reference_price: Decimal | None
    bullish_bos_reference_timestamp: datetime | None
    bullish_bos_protected_low_price: Decimal | None
    bullish_bos_protected_low_timestamp: datetime | None
    bearish_bos_reference_price: Decimal | None
    bearish_bos_reference_timestamp: datetime | None
    bearish_bos_protected_high_price: Decimal | None
    bearish_bos_protected_high_timestamp: datetime | None
    bullish_choch_reference_price: Decimal | None
    bullish_choch_reference_timestamp: datetime | None
    bearish_choch_reference_price: Decimal | None
    bearish_choch_reference_timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class StructureEvent:
    event_type: StructureEventType
    event_timestamp: datetime
    reference_timestamp: datetime
    reference_price: Decimal
    close_price: Decimal


@dataclass(frozen=True, slots=True)
class StructureEngineResult:
    symbol_id: uuid.UUID
    timeframe: Timeframe
    bar_timestamp: datetime
    known_at: datetime
    config_version: str
    pivot_window: int
    swing_points: list[SwingPoint]
    reference_levels: StructureReferenceLevels
    active_range_selection: RangeSelection
    active_range_low: Decimal | None
    active_range_low_timestamp: datetime | None
    active_range_high: Decimal | None
    active_range_high_timestamp: datetime | None
    trend_state: TrendState
    events_on_bar: list[StructureEvent]


@dataclass(frozen=True, slots=True)
class ZoneEngineResult:
    symbol_id: uuid.UUID
    timeframe: Timeframe
    bar_timestamp: datetime
    known_at: datetime
    config_version: str
    range_status: RangeStatus
    selection_reason: RangeSelection
    active_swing_low: Decimal | None
    active_swing_low_timestamp: datetime | None
    active_swing_high: Decimal | None
    active_swing_high_timestamp: datetime | None
    range_width: Decimal | None
    equilibrium: Decimal | None
    equilibrium_band_low: Decimal | None
    equilibrium_band_high: Decimal | None
    zone_location: ZoneLocation
    distance_from_equilibrium: Decimal | None
    distance_from_equilibrium_pct_of_range: Decimal | None


@dataclass(frozen=True, slots=True)
class CompressionResult:
    status: CompressionStatus
    criteria_met: list[CompressionCriterion]
    lookback_bars: int


@dataclass(frozen=True, slots=True)
class DisplacementResult:
    status: DisplacementStatus
    mode: DisplacementMode | None
    event_timestamp: datetime | None
    reference_price: Decimal | None
    reference_timestamp: datetime | None
    range_multiple_atr: Decimal | None
    close_location_ratio: Decimal | None


@dataclass(frozen=True, slots=True)
class LifecyclePatternResult:
    status: LifecycleStatus
    reference_price: Decimal | None
    reference_timestamp: datetime | None
    sweep_low: Decimal | None
    candidate_start_timestamp: datetime | None
    event_timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class TrapReverseResult:
    status: TrapReverseStatus
    reference_price: Decimal | None
    reference_timestamp: datetime | None
    trigger_event: TrapReverseTrigger | None
    event_timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class RecontainmentResult:
    status: RecontainmentStatus
    source_displacement_timestamp: datetime | None
    source_displacement_reference_price: Decimal | None
    candidate_start_timestamp: datetime | None
    active_range_low: Decimal | None
    active_range_high: Decimal | None


@dataclass(frozen=True, slots=True)
class PatternEvent:
    event_type: PatternEventType
    event_timestamp: datetime
    reference_timestamp: datetime | None
    reference_price: Decimal | None


@dataclass(frozen=True, slots=True)
class PatternEngineResult:
    symbol_id: uuid.UUID
    timeframe: Timeframe
    bar_timestamp: datetime
    known_at: datetime
    config_version: str
    compression: CompressionResult
    bullish_displacement: DisplacementResult
    bullish_reclaim: LifecyclePatternResult
    bullish_fake_breakdown: LifecyclePatternResult
    bullish_trap_reverse: TrapReverseResult
    recontainment: RecontainmentResult
    events_on_bar: list[PatternEvent]
    active_flags: list[ActiveFlag]


@dataclass(frozen=True, slots=True)
class SignalFrameInput:
    timeframe: Literal["4H", "1H", "15M", "5M"]
    latest_bar: EngineBar
    structure: StructureEngineResult
    structure_history: list[StructureEngineResult]
    zone: ZoneEngineResult
    pattern: PatternEngineResult


@dataclass(frozen=True, slots=True)
class SignalRegimeInput:
    market_regime: str | None
    sector_regime: str | None
    market_permission_score: Decimal | None
    sector_permission_score: Decimal | None
    allows_longs: bool | None
    coverage_complete: bool
    reason_codes: list[str]
    known_at: datetime


@dataclass(frozen=True, slots=True)
class SignalEventRiskInput:
    event_risk_class: str | None
    blocked: bool | None
    coverage_complete: bool
    soft_penalty: Decimal
    reason_codes: list[str]
    known_at: datetime


@dataclass(frozen=True, slots=True)
class SignalSectorContextInput:
    sector_strength: SectorStrength
    relative_strength_score: Decimal | None
    reason_codes: list[str]
    known_at: datetime


@dataclass(frozen=True, slots=True)
class SignalEngineInput:
    symbol_id: uuid.UUID
    ticker: str
    universe_snapshot_id: uuid.UUID | None
    universe_eligible: bool
    price_reference: Decimal
    universe_reason_codes: list[str]
    universe_known_at: datetime
    htf: SignalFrameInput
    mtf: SignalFrameInput
    ltf: SignalFrameInput
    micro: SignalFrameInput | None
    regime: SignalRegimeInput
    event_risk: SignalEventRiskInput
    sector_context: SignalSectorContextInput


@dataclass(frozen=True, slots=True)
class SignalEngineResult:
    symbol_id: uuid.UUID
    ticker: str
    universe_snapshot_id: uuid.UUID | None
    signal_timestamp: datetime
    known_at: datetime
    htf_bar_timestamp: datetime
    mtf_bar_timestamp: datetime
    ltf_bar_timestamp: datetime
    signal: SignalResultValue
    signal_version: str
    confidence: Decimal
    grade: SignalResultGrade
    bias_htf: SignalBias
    setup_state: OutputSetupState
    reason_codes: list[str]
    event_risk_blocked: bool
    extensible_context: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TradePlanEngineInput:
    signal_id: uuid.UUID
    signal_result: SignalEngineResult
    signal_source: SignalEngineInput


@dataclass(frozen=True, slots=True)
class TradePlanEngineResult:
    signal_id: uuid.UUID
    symbol_id: uuid.UUID
    ticker: str
    plan_timestamp: datetime
    known_at: datetime
    entry_type: TradePlanEntryType
    entry_zone_low: Decimal
    entry_zone_high: Decimal
    confirmation_level: Decimal
    invalidation_level: Decimal
    tp1: Decimal
    tp2: Decimal
    trail_mode: TradePlanTrailMode
    plan_reason_codes: list[str]
    extensible_context: dict[str, Any]
