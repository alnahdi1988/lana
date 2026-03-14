from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.alerts.workflow import AlertWorkflow
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.product.web import create_operator_app
from doctrine_engine.runner.models import RunnerResult, SymbolRunSummary


class _StubProductApp:
    def doctrine_status_snapshot(self):
        return {
            "status": "READY",
            "tracking_timeframe": "15M",
            "time_barrier_bars": 20,
            "open_trades": 1,
            "closed_trades": 0,
        }

    def recent_trades(self, **kwargs):
        ticker = kwargs.get("ticker", "TEST") or "TEST"
        return [
            {
                "signal_id": "trade-signal",
                "symbol_id": "trade-symbol",
                "ticker": ticker,
                "signal": "LONG",
                "confidence": "0.8100",
                "grade": "A",
                "setup_state": "RECONTAINMENT_CONFIRMED",
                "entry_type": "BASE",
                "entry_zone_low": "10.0000",
                "entry_zone_high": "10.5000",
                "confirmation_level": "10.8000",
                "invalidation_level": "9.8000",
                "tp1": "11.2000",
                "tp2": "12.0000",
                "signal_timestamp": "2026-03-11T10:15:00+00:00",
                "known_at": "2026-03-11T10:15:00+00:00",
                "reason_codes": ["PRICE_RANGE_VALID"],
                "micro_state": "AVAILABLE_NOT_USED",
                "outcome_status": "PENDING",
                "first_barrier": None,
                "success_label": None,
                "tp2_label": None,
                "invalidated_first": None,
                "bars_tracked": 0,
                "bars_to_tp1": None,
                "mfe_pct": None,
                "mae_pct": None,
                "tracked_until": None,
                "alert_state": "NEW",
                "suppression_reason": None,
            }
        ]

    def trade_rows_by_signal_ids(self, signal_ids):
        return {
            signal_id: {
                "signal_id": signal_id,
                "ticker": "TEST",
                "outcome_status": "PENDING",
                "first_barrier": None,
                "mfe_pct": None,
                "mae_pct": None,
                "bars_tracked": 0,
            }
            for signal_id in signal_ids
        }

    def enrich_alert_rows(self, alerts):
        trade_map = self.trade_rows_by_signal_ids([row["signal_id"] for row in alerts])
        return [{**row, "trade": trade_map.get(row["signal_id"])} for row in alerts]


def test_operator_web_renders_latest_state(tmp_path):
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
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={
            "market_regime": "BULLISH_TREND",
            "sector_regime": "SECTOR_STRONG",
            "event_risk_class": "NO_EVENT_RISK",
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
    decision = AlertWorkflow().evaluate(
        AlertWorkflowInput(
            signal_id=signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=None,
            snapshot_request_config=None,
        )
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
        rendered_text="preview text",
        transport_result=TelegramSendResult(
            status="SENT",
            message_id="1",
            error_message=None,
            sent_at=known_at,
        ),
    )
    store.record_run(run_result, run_result.symbol_summaries, telegram_sent=1, telegram_failed=0)

    client = TestClient(create_operator_app(store, app_builder=lambda: _StubProductApp()))
    response = client.get("/")
    assert response.status_code == 200
    assert "Doctrine Operator" in response.text
    assert "TEST" in response.text
    assert "preview text" in response.text
    assert "AVAILABLE_NOT_USED" in response.text
    assert "LTF_BULLISH_RECLAIM" in response.text
    assert "True" in response.text
    assert "False" in response.text
    assert "Signal Time" in response.text
    assert "Known At" in response.text
    assert "2026-03-11T10:15:00+00:00" in response.text
    assert "BULLISH_TREND" in response.text
    assert "SECTOR_STRONG" in response.text
    assert "NO_EVENT_RISK" in response.text
    assert "10.0000 - 10.5000" in response.text
    assert "11.2000" in response.text
    assert "PENDING" in response.text
    assert "Doctrine Trades" in response.text
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["latest_run"]["run_status"] == "SUCCESS"
    alerts = client.get("/api/alerts", params={"ticker": "TEST", "micro_state": "AVAILABLE_NOT_USED"})
    assert alerts.status_code == 200
    payload = alerts.json()[0]
    assert payload["micro_state"] == "AVAILABLE_NOT_USED"
    assert payload["market_regime"] == "BULLISH_TREND"
    assert payload["sector_regime"] == "SECTOR_STRONG"
    assert payload["event_risk_class"] == "NO_EVENT_RISK"
    filtered_symbols = client.get("/api/symbols", params={"ticker": "TEST", "alert_state": "NEW"})
    assert filtered_symbols.status_code == 200
    filtered_payload = filtered_symbols.json()
    assert len(filtered_payload) == 1
    assert filtered_payload[0]["ticker"] == "TEST"


def test_operator_web_renders_suppressed_history_symbol_detail_and_recent_errors(tmp_path):
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
        confidence=Decimal("0.7400"),
        grade="B",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={
            "market_regime": "BULLISH_TREND",
            "sector_regime": "SECTOR_STRONG",
            "event_risk_class": "NO_EVENT_RISK",
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
    decision = AlertWorkflow().evaluate(
        AlertWorkflowInput(
            signal_id=signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=None,
            snapshot_request_config=None,
        )
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
        sendable_alerts=0,
        rendered_alerts=0,
        rendered_alert_texts=[],
        symbol_summaries=[
            SymbolRunSummary(
                symbol_id=symbol_id,
                ticker="TEST",
                status="SUCCESS",
                stage_reached="BUILD_ALERT_DECISION",
                signal="LONG",
                ranking_tier="LOW",
                alert_state="SUPPRESSED",
                error_message=None,
            )
        ],
    )
    store.record_alert_event(
        run_id=run_result.run_id,
        signal_id=signal_id,
        decision_result=decision,
        rendered_text=None,
        transport_result=TelegramSendResult(
            status="FAILED",
            message_id=None,
            error_message="telegram down",
            sent_at=None,
        ),
    )
    store.record_run(run_result, run_result.symbol_summaries, telegram_sent=0, telegram_failed=1)
    store.record_error(
        run_id=run_result.run_id,
        symbol_id=symbol_id,
        ticker="TEST",
        stage="BUILD_ALERT_DECISION",
        error_message="workflow warning",
    )

    client = TestClient(create_operator_app(store, app_builder=lambda: _StubProductApp()))
    response = client.get("/")
    assert response.status_code == 200
    assert "GRADE_NOT_SENDABLE" in response.text
    assert "FAILED" in response.text
    assert "telegram down" in response.text
    assert "workflow warning" in response.text

    detail = client.get("/symbols/TEST")
    assert detail.status_code == 200
    assert "Recent Alerts" in detail.text
    assert "GRADE_NOT_SENDABLE" in detail.text
    assert "telegram down" in detail.text
    assert "Tracked Trades" in detail.text

    trades_page = client.get("/trades")
    assert trades_page.status_code == 200
    assert "Doctrine-qualified setups tracked for ML labels" in trades_page.text
    assert "10.0000 - 10.5000" in trades_page.text
