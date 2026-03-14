from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.product.service import DoctrineProductApp
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.product.sync import SyncResult
from doctrine_engine.runner.models import (
    RenderedAlertSummary,
    RunnerInput,
    RunnerResult,
    SymbolRunSummary,
)


class _StubSyncService:
    def prepare_run(self, runner_config):
        return SyncResult(snapshot_id=uuid.uuid4(), synced_tickers=["INTC"], errors=[])


class _StubTransport:
    def send_message(self, text: str) -> TelegramSendResult:
        return TelegramSendResult(
            status="SENT",
            message_id="501",
            error_message=None,
            sent_at=datetime(2026, 3, 14, 8, 0, tzinfo=timezone.utc),
        )


class _StubRunnerPipeline:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, runner_input: RunnerInput) -> RunnerResult:
        workflow = self.kwargs["alert_workflow_factory"](runner_input.config)
        renderer = self.kwargs["telegram_renderer"]
        known_at = datetime(2026, 3, 14, 7, 55, tzinfo=timezone.utc)
        symbol_id = uuid.uuid4()
        signal_id = uuid.uuid4()
        signal = SignalEngineResult(
            symbol_id=symbol_id,
            ticker="INTC",
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
        plan = TradePlanEngineResult(
            signal_id=signal_id,
            symbol_id=symbol_id,
            ticker="INTC",
            plan_timestamp=known_at,
            known_at=known_at,
            entry_type="BASE",
            entry_zone_low=Decimal("10.0"),
            entry_zone_high=Decimal("10.5"),
            confirmation_level=Decimal("10.8"),
            invalidation_level=Decimal("9.8"),
            tp1=Decimal("11.2"),
            tp2=Decimal("12.0"),
            trail_mode="STRUCTURAL",
            plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
            extensible_context={},
        )
        decision = workflow.evaluate(
            AlertWorkflowInput(
                signal_id=signal_id,
                signal_result=signal,
                trade_plan_result=plan,
                prior_alert_state=None,
                snapshot_request_config=None,
            )
        )
        rendered = renderer.render(decision.payload).text
        return RunnerResult(
            run_id=runner_input.run_id,
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
            rendered_alert_texts=[
                RenderedAlertSummary(symbol_id=symbol_id, ticker="INTC", alert_state="NEW", rendered_text=rendered)
            ],
            symbol_summaries=[
                SymbolRunSummary(
                    symbol_id=symbol_id,
                    ticker="INTC",
                    status="SUCCESS",
                    stage_reached="RENDER_ALERT_TEXT",
                    signal="LONG",
                    ranking_tier="HIGH",
                    alert_state="NEW",
                    error_message=None,
                )
            ],
        )


def test_operator_shell_run_once_to_web(tmp_path):
    settings = SimpleNamespace(
        database_url="sqlite://",
        polygon_api_key="polygon-key",
        polygon_base_url="https://api.polygon.io",
        polygon_timeout_seconds=5,
        operator_state_db_path=str(tmp_path / "ops.db"),
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        polygon_universe_refresh_limit=10,
        universe_min_price=Decimal("5"),
        universe_max_price=Decimal("50"),
        universe_min_avg_volume_20d=Decimal("500000"),
        universe_min_avg_dollar_volume_20d=Decimal("5000000"),
        polygon_intraday_lookback_days=30,
        polygon_daily_lookback_days=90,
        phase2_history_window_bars=20,
        polygon_news_lookback_hours=72,
        polygon_news_limit=25,
        halt_status_mode="fail_open",
        alert_cooldown_minutes=60,
        log_level="INFO",
        delayed_data_wording_mode="strict",
        paper_trading_mode=True,
        auto_start_runtime=False,
    )
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = DoctrineProductApp(
        settings=settings,
        state_store=store,
        sync_service=_StubSyncService(),
        telegram_transport=_StubTransport(),
        runner_pipeline_factory=_StubRunnerPipeline,
    )

    run = app.run_once()
    client = TestClient(app.create_operator_app())

    overview = client.get("/")
    run_page = client.get(f"/runs/{run.runner_result.run_id}")
    status = client.get("/api/status")

    assert overview.status_code == 200
    assert "INTC" in overview.text
    assert "AVAILABLE_NOT_USED" in overview.text
    assert run_page.status_code == 200
    assert str(run.runner_result.run_id) in run_page.text
    assert status.status_code == 200
    assert status.json()["health"]["latest_run"]["run_status"] == "SUCCESS"
