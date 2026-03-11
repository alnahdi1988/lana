from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.event_risk.engine import EventRiskEngine
from doctrine_engine.event_risk.models import (
    EarningsCalendarInput,
    EventRiskEngineInput,
    HaltRiskInput,
    NewsRiskInput,
)


def _base_input() -> EventRiskEngineInput:
    return EventRiskEngineInput(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
        earnings=None,
        corporate_events=[],
        news_risks=[],
        halt_risk=None,
    )


def test_abnormal_volume_news_creates_soft_penalty() -> None:
    event_risk_input = replace(
        _base_input(),
        news_risks=[
            NewsRiskInput(
                category="ABNORMAL_VOLUME_NEWS",
                event_datetime=datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 14, 5, tzinfo=timezone.utc),
                severity_score=Decimal("0.90"),
                source="news",
            )
        ],
    )
    result = EventRiskEngine().evaluate(event_risk_input)
    assert result.event_risk_class == "NEWS_ABNORMAL_RISK"
    assert result.blocked is False
    assert result.soft_penalty == Decimal("0.0800")
    assert result.reason_codes[0] == "ABNORMAL_VOLUME_NEWS"


def test_unclear_binary_news_creates_soft_penalty() -> None:
    event_risk_input = replace(
        _base_input(),
        news_risks=[
            NewsRiskInput(
                category="UNCLEAR_BINARY_NEWS",
                event_datetime=datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 14, 5, tzinfo=timezone.utc),
                severity_score=Decimal("0.40"),
                source="news",
            )
        ],
    )
    result = EventRiskEngine().evaluate(event_risk_input)
    assert result.event_risk_class == "NEWS_ABNORMAL_RISK"
    assert result.soft_penalty == Decimal("0.0500")
    assert result.reason_codes[0] == "UNCLEAR_BINARY_NEWS"


def test_mixed_news_inputs_have_deterministic_order_and_capped_penalty() -> None:
    event_risk_input = replace(
        _base_input(),
        news_risks=[
            NewsRiskInput(
                category="UNCLEAR_BINARY_NEWS",
                event_datetime=datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 14, 5, tzinfo=timezone.utc),
                severity_score=Decimal("0.40"),
                source="news",
            ),
            NewsRiskInput(
                category="ABNORMAL_VOLUME_NEWS",
                event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                severity_score=Decimal("0.90"),
                source="news",
            ),
        ],
    )
    result = EventRiskEngine().evaluate(event_risk_input)
    assert result.reason_codes[:2] == ["ABNORMAL_VOLUME_NEWS", "UNCLEAR_BINARY_NEWS"]
    assert result.soft_penalty == Decimal("0.1000")


def test_no_events_is_clear() -> None:
    result = EventRiskEngine().evaluate(_base_input())
    assert result.event_risk_class == "NO_EVENT_RISK"
    assert result.blocked is False
    assert result.soft_penalty == Decimal("0.0000")
    assert result.reason_codes[0] == "EVENT_RISK_CLEAR"


def test_hard_block_omits_news_codes_and_zeroes_penalty() -> None:
    event_risk_input = replace(
        _base_input(),
        earnings=EarningsCalendarInput(
            ticker="TEST",
            earnings_datetime=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
            source="calendar",
        ),
        news_risks=[
            NewsRiskInput(
                category="ABNORMAL_VOLUME_NEWS",
                event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                severity_score=Decimal("0.90"),
                source="news",
            )
        ],
    )
    result = EventRiskEngine().evaluate(event_risk_input)
    assert result.event_risk_class == "EARNINGS_BLOCK"
    assert result.blocked is True
    assert result.soft_penalty == Decimal("0.0000")
    assert result.reason_codes == ["EARNINGS_BLACKOUT_ACTIVE", "EVENT_RISK_PARTIAL_COVERAGE"]


def test_partial_coverage_still_returns_usable_result() -> None:
    event_risk_input = replace(
        _base_input(),
        halt_risk=HaltRiskInput(
            halt_detected=False,
            halt_datetime=None,
            known_at=datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc),
            source="exchange",
        ),
    )
    result = EventRiskEngine().evaluate(event_risk_input)
    assert result.coverage_complete is False
    assert result.reason_codes[-1] == "EVENT_RISK_PARTIAL_COVERAGE"
