from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

EventRiskClass = Literal[
    "NO_EVENT_RISK",
    "EARNINGS_BLOCK",
    "CORPORATE_EVENT_BLOCK",
    "NEWS_ABNORMAL_RISK",
    "HALT_RISK",
]

CorporateEventType = Literal[
    "GUIDANCE",
    "OFFERING",
    "DILUTION",
    "FDA_REGULATORY",
    "MAJOR_CORPORATE_ANNOUNCEMENT",
]

NewsRiskCategory = Literal[
    "ABNORMAL_VOLUME_NEWS",
    "UNCLEAR_BINARY_NEWS",
]


@dataclass(frozen=True, slots=True)
class EarningsCalendarInput:
    ticker: str
    earnings_datetime: datetime | None
    known_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class CorporateEventInput:
    event_type: CorporateEventType
    event_datetime: datetime
    known_at: datetime
    source: str
    blocks_longs: bool


@dataclass(frozen=True, slots=True)
class NewsRiskInput:
    category: NewsRiskCategory
    event_datetime: datetime
    known_at: datetime
    severity_score: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class HaltRiskInput:
    halt_detected: bool
    halt_datetime: datetime | None
    known_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class EventRiskEngineInput:
    symbol_id: uuid.UUID
    ticker: str
    signal_timestamp: datetime
    known_at: datetime
    earnings: EarningsCalendarInput | None
    corporate_events: list[CorporateEventInput] | None
    news_risks: list[NewsRiskInput] | None
    halt_risk: HaltRiskInput | None


@dataclass(frozen=True, slots=True)
class EventRiskEngineConfig:
    config_version: str = "v1"
    earnings_block_days_before: int = 1
    earnings_block_days_after: int = 1
    corporate_block_days_after: int = 2
    halt_block_days_after: int = 2
    abnormal_news_soft_penalty: Decimal = Decimal("0.08")
    unclear_news_soft_penalty: Decimal = Decimal("0.05")
    max_soft_penalty: Decimal = Decimal("0.10")


@dataclass(frozen=True, slots=True)
class EventRiskEngineResult:
    config_version: str
    event_risk_class: EventRiskClass
    blocked: bool
    coverage_complete: bool
    soft_penalty: Decimal
    reason_codes: list[str]
    known_at: datetime
    extensible_context: dict[str, Any]


__all__ = [
    "CorporateEventInput",
    "CorporateEventType",
    "EarningsCalendarInput",
    "EventRiskClass",
    "EventRiskEngineConfig",
    "EventRiskEngineInput",
    "EventRiskEngineResult",
    "HaltRiskInput",
    "NewsRiskCategory",
    "NewsRiskInput",
]
