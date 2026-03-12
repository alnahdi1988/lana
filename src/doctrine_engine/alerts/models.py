from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult

AlertPriority = Literal["PRIORITY", "STANDARD", "LOG_ONLY"]
AlertState = Literal["NEW", "UPGRADED", "SUPPRESSED", "DUPLICATE_BLOCKED", "COOLDOWN_BLOCKED"]
AlertBlockReason = Literal[
    "NOT_LONG",
    "GRADE_NOT_SENDABLE",
    "EVENT_RISK_BLOCKED",
    "DUPLICATE_SIGNAL",
    "COOLDOWN_ACTIVE",
]


@dataclass(frozen=True, slots=True)
class SnapshotRequestConfig:
    enabled: bool
    output_dir: str
    include_timeframes: tuple[Literal["4H", "1H", "15M"], ...] = ("4H", "1H", "15M")
    bars_per_frame: int = 80


@dataclass(frozen=True, slots=True)
class PriorAlertState:
    family_key: str
    signal_id: uuid.UUID
    ticker: str
    signal: str
    confidence: Decimal
    grade: str
    setup_state: str
    entry_type: str
    ltf_trigger_state: str | None
    reason_codes: list[str]
    signal_timestamp: datetime
    known_at: datetime
    sent_at: datetime
    payload_fingerprint: str


@dataclass(frozen=True, slots=True)
class AlertWorkflowInput:
    signal_id: uuid.UUID
    signal_result: SignalEngineResult
    trade_plan_result: TradePlanEngineResult
    prior_alert_state: PriorAlertState | None
    snapshot_request_config: SnapshotRequestConfig | None


@dataclass(frozen=True, slots=True)
class AlertDecisionPayload:
    symbol_id: uuid.UUID
    ticker: str
    signal: Literal["LONG", "NONE"]
    confidence: Decimal
    grade: str
    setup_state: str
    entry_type: str
    entry_zone_low: Decimal
    entry_zone_high: Decimal
    confirmation_level: Decimal
    invalidation_level: Decimal
    tp1: Decimal
    tp2: Decimal
    signal_timestamp: datetime
    known_at: datetime
    alert_state: AlertState
    priority: AlertPriority
    operator_summary: str
    reason_codes: list[str]
    micro_state: str
    micro_present: bool
    micro_trigger_state: str | None
    micro_used_for_confirmation: bool
    snapshot_path: str | None


@dataclass(frozen=True, slots=True)
class SnapshotRenderRequest:
    signal_id: uuid.UUID
    ticker: str
    signal_timestamp: datetime
    known_at: datetime
    entry_zone_low: Decimal
    entry_zone_high: Decimal
    confirmation_level: Decimal
    invalidation_level: Decimal
    tp1: Decimal
    tp2: Decimal
    output_dir: str
    include_timeframes: tuple[Literal["4H", "1H", "15M"], ...]
    bars_per_frame: int


@dataclass(frozen=True, slots=True)
class AlertDecisionResult:
    send: bool
    alert_state: AlertState
    suppression_reason: AlertBlockReason | None
    priority: AlertPriority
    dedup_key: str
    family_key: str
    payload_fingerprint: str
    payload: AlertDecisionPayload
    snapshot_request: SnapshotRenderRequest | None


@dataclass(frozen=True, slots=True)
class TelegramRenderResult:
    text: str


__all__ = [
    "AlertBlockReason",
    "AlertDecisionPayload",
    "AlertDecisionResult",
    "AlertPriority",
    "AlertState",
    "AlertWorkflowInput",
    "PriorAlertState",
    "SnapshotRenderRequest",
    "SnapshotRequestConfig",
    "TelegramRenderResult",
]
