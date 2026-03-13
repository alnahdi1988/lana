from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from doctrine_engine.alerts.workflow import AlertWorkflow
from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.runner.models import RunnerResult, SymbolRunSummary


def _alert_columns(db_path: Path) -> list[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("PRAGMA table_info(alerts)").fetchall()
    finally:
        connection.close()
    return [row[1] for row in rows]


def test_operational_state_store_initialize_creates_micro_columns(tmp_path):
    db_path = tmp_path / "ops.db"

    OperationalStateStore(str(db_path))

    columns = _alert_columns(db_path)

    assert "micro_state" in columns
    assert "micro_present" in columns
    assert "micro_trigger_state" in columns
    assert "micro_used_for_confirmation" in columns
    assert "suppression_reason" in columns
    assert "operator_summary" in columns
    assert "market_regime" in columns
    assert "sector_regime" in columns
    assert "event_risk_class" in columns


def test_operational_state_store_initialize_migrates_existing_alerts_table(tmp_path):
    db_path = tmp_path / "ops.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                symbol_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                setup_state TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                alert_state TEXT NOT NULL,
                send INTEGER NOT NULL,
                family_key TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                signal_timestamp TEXT NOT NULL,
                known_at TEXT NOT NULL,
                reason_codes_json TEXT NOT NULL,
                rendered_text TEXT,
                telegram_status TEXT NOT NULL,
                telegram_message_id TEXT,
                telegram_error TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    OperationalStateStore(str(db_path))

    columns = _alert_columns(db_path)

    assert "micro_state" in columns
    assert "micro_present" in columns
    assert "micro_trigger_state" in columns
    assert "micro_used_for_confirmation" in columns
    assert "suppression_reason" in columns
    assert "operator_summary" in columns
    assert "market_regime" in columns
    assert "sector_regime" in columns
    assert "event_risk_class" in columns


def test_operational_state_store_initialize_is_idempotent_for_micro_columns(tmp_path):
    db_path = tmp_path / "ops.db"

    OperationalStateStore(str(db_path))
    OperationalStateStore(str(db_path))

    columns = _alert_columns(db_path)

    assert columns.count("micro_state") == 1
    assert columns.count("micro_present") == 1
    assert columns.count("micro_trigger_state") == 1
    assert columns.count("micro_used_for_confirmation") == 1
    assert columns.count("suppression_reason") == 1
    assert columns.count("operator_summary") == 1
    assert columns.count("market_regime") == 1
    assert columns.count("sector_regime") == 1
    assert columns.count("event_risk_class") == 1


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
        extensible_context={
            "market_regime": "BULLISH_TREND",
            "sector_regime": "SECTOR_STRONG",
            "event_risk_class": "NO_EVENT_RISK",
            "ltf_trigger_state": "LTF_BULLISH_BOS",
            "micro_state": "AVAILABLE_NOT_USED",
            "micro_present": True,
            "micro_trigger_state": "LTF_BULLISH_RECLAIM",
            "micro_used_for_confirmation": False,
        },
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
    alert = store.recent_alerts(limit=1, suppressed=False)[0]
    assert exact is not None
    assert broader is not None
    assert exact.signal_id == signal_id
    assert broader.signal_id == signal_id
    assert store.latest_run()["run_status"] == "SUCCESS"
    assert alert["telegram_status"] == "SENT"
    assert alert["micro_state"] == "AVAILABLE_NOT_USED"
    assert alert["micro_present"] == 1
    assert alert["micro_trigger_state"] == "LTF_BULLISH_RECLAIM"
    assert alert["micro_used_for_confirmation"] == 0
    assert alert["suppression_reason"] is None
    assert alert["operator_summary"] == decision.payload.operator_summary
    assert alert["market_regime"] == "BULLISH_TREND"
    assert alert["sector_regime"] == "SECTOR_STRONG"
    assert alert["event_risk_class"] == "NO_EVENT_RISK"
