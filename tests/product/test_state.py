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


def _build_signal_result(
    *,
    symbol_id: uuid.UUID | None = None,
    ticker: str = "TEST",
    signal: str = "LONG",
    grade: str = "A",
    setup_state: str = "RECONTAINMENT_CONFIRMED",
    known_at: datetime | None = None,
) -> SignalEngineResult:
    symbol_id = symbol_id or uuid.uuid4()
    known_at = known_at or datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    return SignalEngineResult(
        symbol_id=symbol_id,
        ticker=ticker,
        universe_snapshot_id=None,
        signal_timestamp=known_at,
        known_at=known_at,
        htf_bar_timestamp=known_at,
        mtf_bar_timestamp=known_at,
        ltf_bar_timestamp=known_at,
        signal=signal,
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade=grade,
        bias_htf="BULLISH",
        setup_state=setup_state,
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


def _build_trade_plan_result(
    signal_result: SignalEngineResult,
    *,
    signal_id: uuid.UUID,
    entry_type: str = "BASE",
    entry_zone_high: str = "10.5000",
) -> TradePlanEngineResult:
    return TradePlanEngineResult(
        signal_id=signal_id,
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
        entry_type=entry_type,
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal(entry_zone_high),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("11.2000"),
        tp2=Decimal("12.0000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def _build_decision(
    *,
    symbol_id: uuid.UUID | None = None,
    ticker: str = "TEST",
    signal: str = "LONG",
    grade: str = "A",
    setup_state: str = "RECONTAINMENT_CONFIRMED",
    known_at: datetime | None = None,
    entry_type: str = "BASE",
    entry_zone_high: str = "10.5000",
    prior_alert_state=None,
):
    signal_result = _build_signal_result(
        symbol_id=symbol_id,
        ticker=ticker,
        signal=signal,
        grade=grade,
        setup_state=setup_state,
        known_at=known_at,
    )
    signal_id = uuid.uuid4()
    trade_plan_result = _build_trade_plan_result(
        signal_result,
        signal_id=signal_id,
        entry_type=entry_type,
        entry_zone_high=entry_zone_high,
    )
    decision = AlertWorkflow().evaluate(
        AlertWorkflowInput(
            signal_id=signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=prior_alert_state,
            snapshot_request_config=None,
        )
    )
    return signal_id, signal_result, trade_plan_result, decision


def _build_run_result(
    *,
    run_id: uuid.UUID,
    signal_result: SignalEngineResult,
    alert_state: str,
) -> RunnerResult:
    return RunnerResult(
        run_id=run_id,
        started_at=signal_result.known_at,
        finished_at=signal_result.known_at,
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
                symbol_id=signal_result.symbol_id,
                ticker=signal_result.ticker,
                status="SUCCESS",
                stage_reached="RENDER_ALERT_TEXT",
                signal=signal_result.signal,
                ranking_tier="HIGH",
                alert_state=alert_state,
                error_message=None,
            )
        ],
    )


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


def test_record_run_does_not_promote_skipped_symbols_into_errors(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    symbol_id = uuid.uuid4()
    known_at = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    run_result = RunnerResult(
        run_id=uuid.uuid4(),
        started_at=known_at,
        finished_at=known_at,
        run_status="SUCCESS",
        total_symbols=1,
        succeeded_symbols=0,
        skipped_symbols=1,
        failed_symbols=0,
        generated_signals=1,
        generated_trade_plans=0,
        ranked_symbols=0,
        sendable_alerts=0,
        rendered_alerts=0,
        rendered_alert_texts=[],
        symbol_summaries=[
            SymbolRunSummary(
                symbol_id=symbol_id,
                ticker="IREN",
                status="SKIPPED",
                stage_reached="BUILD_TRADE_PLAN",
                signal="LONG",
                ranking_tier=None,
                alert_state=None,
                error_message="Invalidation anchor cannot fall inside the entry zone.",
            )
        ],
    )

    store.record_run(run_result, run_result.symbol_summaries, telegram_sent=0, telegram_failed=0)

    assert store.latest_run()["failed_symbols"] == 0
    assert store.latest_run_symbols()[0]["status"] == "SKIPPED"
    assert store.recent_errors(limit=10) == []


def test_record_alert_event_persists_duplicate_blocked_without_updating_prior_state(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    symbol_id = uuid.uuid4()

    first_signal_id, first_signal, _, first_decision = _build_decision(
        symbol_id=symbol_id,
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=first_signal_id,
        decision_result=first_decision,
        rendered_text="first alert",
        transport_result=TelegramSendResult(
            status="SENT",
            message_id="101",
            error_message=None,
            sent_at=first_signal.known_at,
        ),
    )

    prior_state = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")
    second_signal_id, second_signal, _, second_decision = _build_decision(
        symbol_id=symbol_id,
        known_at=datetime(2026, 3, 11, 10, 20, tzinfo=timezone.utc),
        prior_alert_state=prior_state,
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=second_signal_id,
        decision_result=second_decision,
        rendered_text=None,
        transport_result=TelegramSendResult(
            status="NOT_SENT",
            message_id=None,
            error_message=second_decision.suppression_reason,
            sent_at=None,
        ),
    )

    latest_alert = store.recent_alerts(limit=1)[0]
    latest_prior = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")

    assert second_decision.alert_state == "DUPLICATE_BLOCKED"
    assert latest_alert["alert_state"] == "DUPLICATE_BLOCKED"
    assert latest_alert["suppression_reason"] == "DUPLICATE_SIGNAL"
    assert latest_alert["telegram_status"] == "NOT_SENT"
    assert latest_prior is not None
    assert latest_prior.signal_id == first_signal_id
    assert latest_prior.known_at == first_signal.known_at
    assert second_signal.known_at > first_signal.known_at


def test_record_alert_event_persists_cooldown_blocked_without_updating_prior_state(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    symbol_id = uuid.uuid4()

    first_signal_id, first_signal, _, first_decision = _build_decision(
        symbol_id=symbol_id,
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=first_signal_id,
        decision_result=first_decision,
        rendered_text="first alert",
        transport_result=TelegramSendResult(
            status="SENT",
            message_id="201",
            error_message=None,
            sent_at=first_signal.known_at,
        ),
    )

    prior_state = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")
    second_signal_id, _, _, second_decision = _build_decision(
        symbol_id=symbol_id,
        known_at=datetime(2026, 3, 11, 10, 20, tzinfo=timezone.utc),
        entry_zone_high="10.6500",
        prior_alert_state=prior_state,
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=second_signal_id,
        decision_result=second_decision,
        rendered_text=None,
        transport_result=TelegramSendResult(
            status="NOT_SENT",
            message_id=None,
            error_message=second_decision.suppression_reason,
            sent_at=None,
        ),
    )

    latest_alert = store.recent_alerts(limit=1)[0]
    latest_prior = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")

    assert second_decision.alert_state == "COOLDOWN_BLOCKED"
    assert latest_alert["alert_state"] == "COOLDOWN_BLOCKED"
    assert latest_alert["suppression_reason"] == "COOLDOWN_ACTIVE"
    assert latest_alert["telegram_status"] == "NOT_SENT"
    assert latest_prior is not None
    assert latest_prior.signal_id == first_signal_id


def test_record_alert_event_persists_upgrade_and_updates_prior_state(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    symbol_id = uuid.uuid4()

    first_signal_id, first_signal, _, first_decision = _build_decision(
        symbol_id=symbol_id,
        grade="A",
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=first_signal_id,
        decision_result=first_decision,
        rendered_text="first alert",
        transport_result=TelegramSendResult(
            status="SENT",
            message_id="301",
            error_message=None,
            sent_at=first_signal.known_at,
        ),
    )

    prior_state = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")
    second_signal_id, second_signal, _, second_decision = _build_decision(
        symbol_id=symbol_id,
        grade="A+",
        known_at=datetime(2026, 3, 11, 10, 20, tzinfo=timezone.utc),
        prior_alert_state=prior_state,
    )
    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=second_signal_id,
        decision_result=second_decision,
        rendered_text="upgraded alert",
        transport_result=TelegramSendResult(
            status="SENT",
            message_id="302",
            error_message=None,
            sent_at=second_signal.known_at,
        ),
    )

    latest_alert = store.recent_alerts(limit=1)[0]
    latest_prior = store.load_prior_alert_state(symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")

    assert second_decision.alert_state == "UPGRADED"
    assert latest_alert["alert_state"] == "UPGRADED"
    assert latest_alert["telegram_status"] == "SENT"
    assert latest_prior is not None
    assert latest_prior.signal_id == second_signal_id
    assert latest_prior.grade == "A+"


def test_record_alert_event_persists_failed_transport_and_error_row(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    signal_id, signal_result, _, decision = _build_decision()

    store.record_alert_event(
        run_id=uuid.uuid4(),
        signal_id=signal_id,
        decision_result=decision,
        rendered_text="alert text",
        transport_result=TelegramSendResult(
            status="FAILED",
            message_id=None,
            error_message="telegram down",
            sent_at=None,
        ),
    )

    alert = store.recent_alerts(limit=1)[0]
    error = store.recent_errors(limit=1)[0]
    prior = store.load_prior_alert_state(signal_result.symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")

    assert alert["telegram_status"] == "FAILED"
    assert alert["telegram_error"] == "telegram down"
    assert error["ticker"] == signal_result.ticker
    assert error["stage"] == "TELEGRAM_SEND"
    assert error["error_message"] == "telegram down"
    assert prior is None


def test_record_alert_event_persists_non_sent_transport_without_error_row(tmp_path):
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    signal_id, signal_result, _, decision = _build_decision()

    for status, error_message in (
        ("SKIPPED_DISABLED", None),
        ("SKIPPED_UNCONFIGURED", "Telegram bot token and chat id are required."),
    ):
        store.record_alert_event(
            run_id=uuid.uuid4(),
            signal_id=uuid.uuid4(),
            decision_result=decision,
            rendered_text="alert text",
            transport_result=TelegramSendResult(
                status=status,
                message_id=None,
                error_message=error_message,
                sent_at=None,
            ),
        )

    alerts = store.recent_alerts(limit=2)
    statuses = {alert["telegram_status"] for alert in alerts}
    errors = store.recent_errors(limit=10)
    prior = store.load_prior_alert_state(signal_result.symbol_id, "RECONTAINMENT_CONFIRMED", "BASE")

    assert statuses == {"SKIPPED_DISABLED", "SKIPPED_UNCONFIGURED"}
    assert errors == []
    assert prior is None
