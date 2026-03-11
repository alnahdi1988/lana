from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.event_risk.engine import EventRiskEngine
from doctrine_engine.event_risk.models import (
    CorporateEventInput,
    EarningsCalendarInput,
    EventRiskEngineConfig,
    EventRiskEngineInput,
    HaltRiskInput,
    NewsRiskInput,
)


def _base_input(**overrides) -> EventRiskEngineInput:
    base = EventRiskEngineInput(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
        earnings=None,
        corporate_events=[],
        news_risks=[],
        halt_risk=None,
    )
    return replace(base, **overrides)


def test_earnings_blackout_active_blocks() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            earnings=EarningsCalendarInput(
                ticker="TEST",
                earnings_datetime=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
                source="calendar",
            )
        )
    )
    assert result.event_risk_class == "EARNINGS_BLOCK"
    assert result.blocked is True
    assert result.reason_codes[0] == "EARNINGS_BLACKOUT_ACTIVE"


def test_earnings_outside_window_is_clear() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            signal_timestamp=datetime(2026, 3, 14, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 14, 16, 0, tzinfo=timezone.utc),
            earnings=EarningsCalendarInput(
                ticker="TEST",
                earnings_datetime=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
                source="calendar",
            ),
        )
    )
    assert result.event_risk_class == "NO_EVENT_RISK"
    assert result.blocked is False
    assert result.reason_codes[0] == "EVENT_RISK_CLEAR"


def test_corporate_block_active_within_window() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            corporate_events=[
                CorporateEventInput(
                    event_type="OFFERING",
                    event_datetime=datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 9, 10, 5, tzinfo=timezone.utc),
                    source="newswire",
                    blocks_longs=True,
                )
            ]
        )
    )
    assert result.event_risk_class == "CORPORATE_EVENT_BLOCK"
    assert result.blocked is True
    assert result.reason_codes[0] == "CORPORATE_EVENT_BLOCKED"


def test_corporate_block_expires_after_window() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            signal_timestamp=datetime(2026, 3, 13, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 13, 16, 0, tzinfo=timezone.utc),
            corporate_events=[
                CorporateEventInput(
                    event_type="OFFERING",
                    event_datetime=datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 9, 10, 5, tzinfo=timezone.utc),
                    source="newswire",
                    blocks_longs=True,
                )
            ],
        )
    )
    assert result.event_risk_class == "NO_EVENT_RISK"
    assert result.blocked is False


def test_halt_block_active_within_window() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            halt_risk=HaltRiskInput(
                halt_detected=True,
                halt_datetime=datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 9, 14, 1, tzinfo=timezone.utc),
                source="exchange",
            )
        )
    )
    assert result.event_risk_class == "HALT_RISK"
    assert result.blocked is True
    assert result.reason_codes[0] == "HALT_RISK_BLOCKED"


def test_halt_block_expires_after_window() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            signal_timestamp=datetime(2026, 3, 13, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 13, 16, 0, tzinfo=timezone.utc),
            halt_risk=HaltRiskInput(
                halt_detected=True,
                halt_datetime=datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 9, 14, 1, tzinfo=timezone.utc),
                source="exchange",
            ),
        )
    )
    assert result.event_risk_class == "NO_EVENT_RISK"
    assert result.blocked is False


def test_precedence_halt_beats_earnings_corporate_and_news() -> None:
    result = EventRiskEngine().evaluate(
        _base_input(
            earnings=EarningsCalendarInput(
                ticker="TEST",
                earnings_datetime=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
                source="calendar",
            ),
            corporate_events=[
                CorporateEventInput(
                    event_type="GUIDANCE",
                    event_datetime=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 12, 5, tzinfo=timezone.utc),
                    source="newswire",
                    blocks_longs=True,
                )
            ],
            news_risks=[
                NewsRiskInput(
                    category="ABNORMAL_VOLUME_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                    severity_score=Decimal("0.90"),
                    source="news",
                )
            ],
            halt_risk=HaltRiskInput(
                halt_detected=True,
                halt_datetime=datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 14, 1, tzinfo=timezone.utc),
                source="exchange",
            ),
        )
    )
    assert result.event_risk_class == "HALT_RISK"
    assert result.blocked is True
    assert result.soft_penalty == Decimal("0.0000")
    assert result.reason_codes[0] == "HALT_RISK_BLOCKED"


def test_custom_finite_windows_are_honored() -> None:
    engine = EventRiskEngine(
        EventRiskEngineConfig(
            earnings_block_days_before=0,
            earnings_block_days_after=0,
            corporate_block_days_after=1,
            halt_block_days_after=1,
        )
    )
    result = engine.evaluate(
        _base_input(
            signal_timestamp=datetime(2026, 3, 12, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 12, 16, 0, tzinfo=timezone.utc),
            earnings=EarningsCalendarInput(
                ticker="TEST",
                earnings_datetime=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
                source="calendar",
            ),
            corporate_events=[
                CorporateEventInput(
                    event_type="OFFERING",
                    event_datetime=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 10, 1, tzinfo=timezone.utc),
                    source="newswire",
                    blocks_longs=True,
                )
            ],
            halt_risk=HaltRiskInput(
                halt_detected=True,
                halt_datetime=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 10, 1, tzinfo=timezone.utc),
                source="exchange",
            ),
        )
    )
    assert result.event_risk_class == "NO_EVENT_RISK"
