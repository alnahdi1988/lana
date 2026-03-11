from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.alerts.models import AlertWorkflowInput, PriorAlertState
from doctrine_engine.alerts.workflow import AlertWorkflow, AlertWorkflowConfig
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult


def _signal_result(*, grade: str = "A", setup_state: str = "RECONTAINMENT_CONFIRMED") -> SignalEngineResult:
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
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade=grade,
        bias_htf="BULLISH",
        setup_state=setup_state,
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": "LTF_BULLISH_CHOCH"},
    )


def _trade_plan_result(signal_result: SignalEngineResult, *, entry_type: str = "BASE", zone_high: str = "10.5500") -> TradePlanEngineResult:
    return TradePlanEngineResult(
        signal_id=uuid.uuid4(),
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
        entry_type=entry_type,
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal(zone_high),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("10.9500"),
        tp2=Decimal("11.3000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def _evaluate(signal_result: SignalEngineResult, trade_plan_result: TradePlanEngineResult, prior_alert_state: PriorAlertState | None) -> tuple:
    workflow = AlertWorkflow(AlertWorkflowConfig(cooldown_minutes=60))
    result = workflow.evaluate(
        AlertWorkflowInput(
            signal_id=trade_plan_result.signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=prior_alert_state,
            snapshot_request_config=None,
        )
    )
    return workflow, result


def _prior_from_result(result, sent_at: datetime | None = None) -> PriorAlertState:
    return PriorAlertState(
        family_key=result.family_key,
        signal_id=uuid.UUID(result.dedup_key),
        ticker=result.payload.ticker,
        signal=result.payload.signal,
        confidence=result.payload.confidence,
        grade=result.payload.grade,
        setup_state=result.payload.setup_state,
        entry_type=result.payload.entry_type,
        ltf_trigger_state="LTF_BULLISH_CHOCH",
        reason_codes=list(result.payload.reason_codes),
        signal_timestamp=result.payload.signal_timestamp,
        known_at=result.payload.known_at,
        sent_at=sent_at or result.payload.known_at,
        payload_fingerprint=result.payload_fingerprint,
    )


def test_same_signal_id_is_duplicate_blocked() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    _, first = _evaluate(signal_result, trade_plan_result, None)
    prior = _prior_from_result(first)

    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(trade_plan_result.signal_id, signal_result, trade_plan_result, prior, None)
    )

    assert second.send is False
    assert second.alert_state == "DUPLICATE_BLOCKED"
    assert second.suppression_reason == "DUPLICATE_SIGNAL"


def test_same_family_same_fingerprint_inside_cooldown_is_duplicate_blocked() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    _, first = _evaluate(signal_result, trade_plan_result, None)
    prior = _prior_from_result(first, sent_at=signal_result.known_at - timedelta(minutes=10))

    new_trade_plan = replace(trade_plan_result, signal_id=uuid.uuid4())
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(new_trade_plan.signal_id, signal_result, new_trade_plan, prior, None)
    )

    assert second.send is False
    assert second.alert_state == "DUPLICATE_BLOCKED"


def test_same_family_different_fingerprint_inside_cooldown_without_upgrade_is_cooldown_blocked() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    _, first = _evaluate(signal_result, trade_plan_result, None)
    prior = _prior_from_result(first, sent_at=signal_result.known_at - timedelta(minutes=10))

    changed_trade_plan = replace(trade_plan_result, signal_id=uuid.uuid4(), entry_zone_high=Decimal("10.6500"))
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(changed_trade_plan.signal_id, signal_result, changed_trade_plan, prior, None)
    )

    assert second.send is False
    assert second.alert_state == "COOLDOWN_BLOCKED"
    assert second.suppression_reason == "COOLDOWN_ACTIVE"


def test_grade_upgrade_inside_cooldown_is_upgraded() -> None:
    prior_signal = _signal_result(grade="A")
    prior_trade_plan = _trade_plan_result(prior_signal, entry_type="BASE")
    _, first = _evaluate(prior_signal, prior_trade_plan, None)
    prior = _prior_from_result(first, sent_at=prior_signal.known_at - timedelta(minutes=10))

    current_signal = replace(prior_signal, grade="A+")
    current_trade_plan = replace(prior_trade_plan, signal_id=uuid.uuid4())
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(current_trade_plan.signal_id, current_signal, current_trade_plan, prior, None)
    )

    assert second.send is True
    assert second.alert_state == "UPGRADED"


def test_entry_type_upgrade_inside_cooldown_is_upgraded() -> None:
    signal_result = _signal_result()
    base_trade_plan = _trade_plan_result(signal_result, entry_type="BASE")
    _, first = _evaluate(signal_result, base_trade_plan, None)
    prior = _prior_from_result(first, sent_at=signal_result.known_at - timedelta(minutes=10))

    confirmation_trade_plan = replace(base_trade_plan, signal_id=uuid.uuid4(), entry_type="CONFIRMATION")
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(confirmation_trade_plan.signal_id, signal_result, confirmation_trade_plan, prior, None)
    )

    assert second.send is True
    assert second.alert_state == "UPGRADED"


def test_different_family_key_is_new() -> None:
    signal_result = _signal_result(setup_state="RECONTAINMENT_CONFIRMED")
    trade_plan_result = _trade_plan_result(signal_result, entry_type="BASE")
    _, first = _evaluate(signal_result, trade_plan_result, None)
    prior = _prior_from_result(first, sent_at=signal_result.known_at - timedelta(minutes=10))

    different_signal = replace(signal_result, setup_state="DISCOUNT_RESPONSE")
    different_trade_plan = replace(trade_plan_result, signal_id=uuid.uuid4(), entry_type="CONFIRMATION")
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(different_trade_plan.signal_id, different_signal, different_trade_plan, prior, None)
    )

    assert second.send is True
    assert second.alert_state == "NEW"


def test_cooldown_expired_identical_fingerprint_is_new() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    _, first = _evaluate(signal_result, trade_plan_result, None)
    prior = _prior_from_result(first, sent_at=signal_result.known_at - timedelta(minutes=61))

    new_trade_plan = replace(trade_plan_result, signal_id=uuid.uuid4())
    second = AlertWorkflow().evaluate(
        AlertWorkflowInput(new_trade_plan.signal_id, signal_result, new_trade_plan, prior, None)
    )

    assert second.send is True
    assert second.alert_state == "NEW"
