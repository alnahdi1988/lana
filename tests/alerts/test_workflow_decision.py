from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.alerts.workflow import AlertWorkflow
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult


def _signal_result(*, signal: str = "LONG", grade: str = "A", event_risk_blocked: bool = False) -> SignalEngineResult:
    ts = datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc)
    return SignalEngineResult(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        universe_snapshot_id=None,
        signal_timestamp=ts,
        known_at=datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc),
        htf_bar_timestamp=datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc),
        mtf_bar_timestamp=datetime(2026, 3, 8, 15, 0, tzinfo=timezone.utc),
        ltf_bar_timestamp=ts,
        signal=signal,
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade=grade,
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE", "HTF_BULLISH_STRUCTURE"],
        event_risk_blocked=event_risk_blocked,
        extensible_context={"ltf_trigger_state": "LTF_BULLISH_CHOCH"},
    )


def _trade_plan_result(signal_result: SignalEngineResult) -> TradePlanEngineResult:
    return TradePlanEngineResult(
        signal_id=uuid.uuid4(),
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5500"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("10.9500"),
        tp2=Decimal("11.3000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def test_a_plus_long_is_new_priority() -> None:
    signal_result = _signal_result(grade="A+")
    trade_plan_result = _trade_plan_result(signal_result)
    workflow_input = AlertWorkflowInput(
        signal_id=trade_plan_result.signal_id,
        signal_result=signal_result,
        trade_plan_result=trade_plan_result,
        prior_alert_state=None,
        snapshot_request_config=None,
    )

    result = AlertWorkflow().evaluate(workflow_input)

    assert result.send is True
    assert result.alert_state == "NEW"
    assert result.priority == "PRIORITY"
    assert result.payload.reason_codes == signal_result.reason_codes


def test_a_long_is_new_standard() -> None:
    signal_result = _signal_result(grade="A")
    trade_plan_result = _trade_plan_result(signal_result)

    result = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, None, None)
    )

    assert result.send is True
    assert result.alert_state == "NEW"
    assert result.priority == "STANDARD"


def test_b_long_is_suppressed_and_log_only() -> None:
    signal_result = _signal_result(grade="B")
    trade_plan_result = _trade_plan_result(signal_result)

    result = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, None, None)
    )

    assert result.send is False
    assert result.alert_state == "SUPPRESSED"
    assert result.suppression_reason == "GRADE_NOT_SENDABLE"
    assert result.priority == "LOG_ONLY"


def test_none_signal_is_suppressed() -> None:
    signal_result = _signal_result(signal="NONE", grade="IGNORE")
    trade_plan_result = _trade_plan_result(signal_result)

    result = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, None, None)
    )

    assert result.send is False
    assert result.alert_state == "SUPPRESSED"
    assert result.suppression_reason == "NOT_LONG"


def test_event_risk_blocked_is_suppressed() -> None:
    signal_result = _signal_result(event_risk_blocked=True)
    trade_plan_result = _trade_plan_result(signal_result)

    result = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, None, None)
    )

    assert result.send is False
    assert result.alert_state == "SUPPRESSED"
    assert result.suppression_reason == "EVENT_RISK_BLOCKED"


def test_signal_trade_plan_mismatch_raises_value_error() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    bad_trade_plan = replace(trade_plan_result, ticker="OTHER")

    with pytest.raises(ValueError, match="ticker"):
        AlertWorkflow().evaluate(
            AlertWorkflowInput(bad_trade_plan.signal_id, signal_result, bad_trade_plan, None, None)
        )


def test_payload_reason_codes_match_exact_signal_result_order() -> None:
    signal_result = replace(
        _signal_result(),
        reason_codes=["Z_CODE", "A_CODE", "A_CODE", "M_CODE"],
    )
    trade_plan_result = _trade_plan_result(signal_result)

    result = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, None, None)
    )

    assert result.payload.reason_codes == ["Z_CODE", "A_CODE", "A_CODE", "M_CODE"]
