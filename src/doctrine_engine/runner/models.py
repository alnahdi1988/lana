from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from doctrine_engine.engines.models import (
    EngineBar,
    PatternEngineResult,
    StructureEngineResult,
    ZoneEngineResult,
)
from doctrine_engine.regime.models import RegimeIndexInput

RunMode = Literal["ONCE", "SCHEDULED"]
RunStatus = Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"]
StageName = Literal[
    "LOAD_UNIVERSE_CONTEXT",
    "LOAD_PHASE2_CONTEXT",
    "BUILD_REGIME",
    "BUILD_EVENT_RISK",
    "BUILD_SIGNAL",
    "BUILD_TRADE_PLAN",
    "BUILD_RANKING",
    "BUILD_ALERT_DECISION",
    "RENDER_ALERT_TEXT",
    "EMIT_RUN_SUMMARY",
]
StageStatus = Literal["SUCCESS", "SKIPPED", "FAILED"]

STAGE_ORDER: tuple[StageName, ...] = (
    "LOAD_UNIVERSE_CONTEXT",
    "LOAD_PHASE2_CONTEXT",
    "BUILD_REGIME",
    "BUILD_EVENT_RISK",
    "BUILD_SIGNAL",
    "BUILD_TRADE_PLAN",
    "BUILD_RANKING",
    "BUILD_ALERT_DECISION",
    "RENDER_ALERT_TEXT",
    "EMIT_RUN_SUMMARY",
)


@dataclass(frozen=True, slots=True)
class UniverseSelectionConfig:
    max_symbols_per_run: int | None
    include_tickers: tuple[str, ...] = ()
    exclude_tickers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TimeframeConfig:
    htf: Literal["4H"] = "4H"
    mtf: Literal["1H"] = "1H"
    ltf: Literal["15M"] = "15M"
    micro: Literal["5M"] | None = None


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    config_version: str = "v1"
    run_mode: RunMode = "ONCE"
    fail_fast: bool = False
    continue_on_symbol_error: bool = True
    max_symbol_failures_before_abort: int = 25
    external_read_retry_attempts: int = 2
    external_read_retry_backoff_ms: int = 250
    universe: UniverseSelectionConfig = UniverseSelectionConfig(max_symbols_per_run=None)
    timeframes: TimeframeConfig = TimeframeConfig()
    require_micro_confirmation: bool = False
    enable_ranking: bool = True
    enable_alert_workflow: bool = True
    enable_snapshot_requests: bool = False
    alert_cooldown_minutes: int = 60


@dataclass(frozen=True, slots=True)
class RunnerInput:
    run_id: uuid.UUID
    triggered_at: datetime
    config: RunnerConfig


@dataclass(frozen=True, slots=True)
class UniverseSymbolContext:
    symbol_id: uuid.UUID
    ticker: str
    universe_snapshot_id: uuid.UUID | None
    universe_eligible: bool
    price_reference: Decimal
    universe_reason_codes: list[str]
    universe_known_at: datetime


@dataclass(frozen=True, slots=True)
class PersistedFramePhase2Context:
    structure: StructureEngineResult
    structure_history: list[StructureEngineResult]
    zone: ZoneEngineResult
    pattern: PatternEngineResult


@dataclass(frozen=True, slots=True)
class PersistedPhase2Context:
    htf: PersistedFramePhase2Context
    mtf: PersistedFramePhase2Context
    ltf: PersistedFramePhase2Context
    micro: PersistedFramePhase2Context | None


@dataclass(frozen=True, slots=True)
class SymbolMarketContext:
    htf_bar: EngineBar
    mtf_bar: EngineBar
    ltf_bar: EngineBar
    micro_bar: EngineBar | None


@dataclass(frozen=True, slots=True)
class BenchmarkPhaseContext:
    market_indexes: list[RegimeIndexInput]


@dataclass(frozen=True, slots=True)
class RenderedAlertSummary:
    symbol_id: uuid.UUID
    ticker: str
    alert_state: str
    rendered_text: str


@dataclass(frozen=True, slots=True)
class SymbolRunSummary:
    symbol_id: uuid.UUID
    ticker: str
    status: Literal["SUCCESS", "SKIPPED", "FAILED"]
    stage_reached: StageName
    signal: str | None
    ranking_tier: str | None
    alert_state: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class RunnerResult:
    run_id: uuid.UUID
    started_at: datetime
    finished_at: datetime
    run_status: RunStatus
    total_symbols: int
    succeeded_symbols: int
    skipped_symbols: int
    failed_symbols: int
    generated_signals: int
    generated_trade_plans: int
    ranked_symbols: int
    sendable_alerts: int
    rendered_alerts: int
    rendered_alert_texts: list[RenderedAlertSummary]
    symbol_summaries: list[SymbolRunSummary]


__all__ = [
    "BenchmarkPhaseContext",
    "PersistedFramePhase2Context",
    "PersistedPhase2Context",
    "RenderedAlertSummary",
    "RunnerConfig",
    "RunnerInput",
    "RunnerResult",
    "RunMode",
    "RunStatus",
    "STAGE_ORDER",
    "StageName",
    "StageStatus",
    "SymbolMarketContext",
    "SymbolRunSummary",
    "TimeframeConfig",
    "UniverseSelectionConfig",
    "UniverseSymbolContext",
]
