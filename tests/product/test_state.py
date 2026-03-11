from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.alerts.workflow import AlertWorkflow
from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.runner.models import RunnerResult, SymbolRunSummary


def test_operational_state_store_round_trip(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    signal_id = uuid.uuid4()
    symbol_id = uuid.uuid4()
    known_at = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    signal_result = SignalEngineResult(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        signal_timestamp=known_at,
        known_at=known_at,
        htf_bar_timestamp=known_at,
        mtf_bar_timestamp=known_at,
        ltf_bar_timestamp=known_at,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade="A",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": "LTF_BULLISH_BOS"},
    )
    trade_plan_result = TradePlanEngineResult(
        signal_id=signal_id,
        symbol_id=symbol_id,
        ticker="TEST",
        plan_timestamp=known_at,
        known_at=known_at,
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5000"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("11.2000"),
        tp2=Decimal("12.0000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )
    workflow = AlertWorkflow()
    decision = workflow.evaluate(
        AlertWorkflowInput(
            signal_id=signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=None,
            snapshot_request_config=None,
        )
    )
    transport = TelegramSendResult(
        status="SENT",
        message_id="123",
        error_message=None,
        sent_at=known_at,
    )
    run_result = RunnerResult(
        run_id=uuid.uuid4(),
        started_at=known_at,
        finished_at=known_at,
        run_status="SUCCESS",
        total_symbols=1,
        succeeded_symbols=1,
        skipped_symbols=0,
        failed_symbols=0,
        generated_signals=1,
        generated_trade_plans=1,
        ranked_symbols=1,
        sendable_alerts=1,
        rendered_alerts=1,
        rendered_alert_texts=[],
        symbol_summaries=[
            SymbolRunSummary(
                symbol_id=symbol_id,
                ticker="TEST",
                status="SUCCESS",
                stage_reached="RENDER_ALERT_TEXT",
                signal="LONG",
                ranking_tier="HIGH",
                alert_state="NEW",
                error_message=None,
            )
        ],
    )

    store.record_alert_event(
        run_id=run_result.run_id,
        signal_id=signal_id,
        decision_result=decision,
        rendered_text="alert text",
        transport_result=transport,
    )
    store.record_run(run_result, run_result.symbol_summaries, telegram_sent=1, telegram_failed=0)

    exact = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")
    broader = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "CONFIRMATION")
    assert exact is not None
    assert broader is not None
    assert exact.signal_id == signal_id
    assert broader.signal_id == signal_id
    assert store.latest_run()["run_status"] == "SUCCESS"
    assert store.recent_alerts(limit=1, suppressed=False)[0]["telegram_status"] == "SENT"

