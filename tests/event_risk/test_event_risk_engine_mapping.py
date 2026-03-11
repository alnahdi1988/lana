from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from doctrine_engine.engines.models import SignalEventRiskInput
from doctrine_engine.event_risk.engine import EventRiskEngine
from doctrine_engine.event_risk.models import (
    EarningsCalendarInput,
    EventRiskEngineInput,
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


def test_output_maps_directly_into_signal_event_risk_input() -> None:
    result = EventRiskEngine().evaluate(
        EventRiskEngineInput(
            symbol_id=uuid.uuid4(),
            ticker="TEST",
            signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
            earnings=None,
            corporate_events=[],
            news_risks=[
                NewsRiskInput(
                    category="ABNORMAL_VOLUME_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                    severity_score=Decimal("0.90"),
                    source="news",
                )
            ],
            halt_risk=None,
        )
    )
    mapped = SignalEventRiskInput(
        event_risk_class=result.event_risk_class,
        blocked=result.blocked,
        coverage_complete=result.coverage_complete,
        soft_penalty=result.soft_penalty,
        reason_codes=result.reason_codes,
        known_at=result.known_at,
    )
    assert mapped.event_risk_class == "NEWS_ABNORMAL_RISK"
    assert mapped.blocked is False
    assert mapped.soft_penalty == Decimal("0.0800")
    assert mapped.reason_codes == ["ABNORMAL_VOLUME_NEWS", "EVENT_RISK_PARTIAL_COVERAGE"]


def test_known_at_uses_max_consumed_input_or_baseline_if_none() -> None:
    baseline_result = EventRiskEngine().evaluate(_base_input())
    assert baseline_result.known_at == datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc)

    consumed_result = EventRiskEngine().evaluate(
        EventRiskEngineInput(
            symbol_id=uuid.uuid4(),
            ticker="TEST",
            signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
            earnings=EarningsCalendarInput(
                ticker="TEST",
                earnings_datetime=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 15, 50, tzinfo=timezone.utc),
                source="calendar",
            ),
            corporate_events=[],
            news_risks=[
                NewsRiskInput(
                    category="ABNORMAL_VOLUME_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 15, 55, tzinfo=timezone.utc),
                    severity_score=Decimal("0.20"),
                    source="news",
                )
            ],
            halt_risk=None,
        )
    )
    assert consumed_result.known_at == datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc)


def test_future_known_event_relative_to_baseline_raises() -> None:
    with pytest.raises(ValueError):
        EventRiskEngine().evaluate(
            EventRiskEngineInput(
                symbol_id=uuid.uuid4(),
                ticker="TEST",
                signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
                earnings=EarningsCalendarInput(
                    ticker="TEST",
                    earnings_datetime=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 16, 1, tzinfo=timezone.utc),
                    source="calendar",
                ),
                corporate_events=[],
                news_risks=[],
                halt_risk=None,
            )
        )


def test_reason_code_ordering_is_deterministic_for_news_and_partial_coverage() -> None:
    result = EventRiskEngine().evaluate(
        EventRiskEngineInput(
            symbol_id=uuid.uuid4(),
            ticker="TEST",
            signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
            earnings=None,
            corporate_events=[],
            news_risks=[
                NewsRiskInput(
                    category="UNCLEAR_BINARY_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 30, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 13, 35, tzinfo=timezone.utc),
                    severity_score=Decimal("0.10"),
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
            halt_risk=None,
        )
    )
    assert result.reason_codes == [
        "ABNORMAL_VOLUME_NEWS",
        "UNCLEAR_BINARY_NEWS",
        "EVENT_RISK_PARTIAL_COVERAGE",
    ]


def test_severity_score_is_informational_only_in_phase_7() -> None:
    low = EventRiskEngine().evaluate(
        EventRiskEngineInput(
            symbol_id=uuid.uuid4(),
            ticker="TEST",
            signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
            earnings=None,
            corporate_events=[],
            news_risks=[
                NewsRiskInput(
                    category="ABNORMAL_VOLUME_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                    severity_score=Decimal("0.10"),
                    source="news",
                )
            ],
            halt_risk=None,
        )
    )
    high = EventRiskEngine().evaluate(
        EventRiskEngineInput(
            symbol_id=uuid.uuid4(),
            ticker="TEST",
            signal_timestamp=datetime(2026, 3, 10, 15, 45, tzinfo=timezone.utc),
            known_at=datetime(2026, 3, 10, 16, 0, tzinfo=timezone.utc),
            earnings=None,
            corporate_events=[],
            news_risks=[
                NewsRiskInput(
                    category="ABNORMAL_VOLUME_NEWS",
                    event_datetime=datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
                    known_at=datetime(2026, 3, 10, 13, 5, tzinfo=timezone.utc),
                    severity_score=Decimal("0.95"),
                    source="news",
                )
            ],
            halt_risk=None,
        )
    )
    assert low.soft_penalty == Decimal("0.0800")
    assert high.soft_penalty == Decimal("0.0800")
