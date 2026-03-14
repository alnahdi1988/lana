from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from doctrine_engine.product.adapters import DbPhase2FeatureLoader
from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.product.service import DoctrineProductApp
from doctrine_engine.product.sync import SyncResult
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.runner.models import (
    RenderedAlertSummary,
    RunnerConfig,
    RunnerInput,
    RunnerResult,
    SymbolRunSummary,
    TimeframeConfig,
    UniverseSelectionConfig,
    UniverseSymbolContext,
)


class _StubSyncService:
    def prepare_run(self, runner_config):
        return SyncResult(snapshot_id=uuid.uuid4(), synced_tickers=["TEST"], errors=[])


class _StubTransport:
    def send_message(self, text: str) -> TelegramSendResult:
        return TelegramSendResult(
            status="SENT",
            message_id="99",
            error_message=None,
            sent_at=datetime(2026, 3, 11, 10, 16, tzinfo=timezone.utc),
        )


class _StubRunnerPipeline:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, runner_input: RunnerInput) -> RunnerResult:
        workflow = self.kwargs["alert_workflow_factory"](runner_input.config)
        renderer = self.kwargs["telegram_renderer"]
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
        decision = workflow.evaluate(
            AlertWorkflowInput(
                signal_id=signal_id,
                signal_result=signal_result,
                trade_plan_result=trade_plan_result,
                prior_alert_state=None,
                snapshot_request_config=None,
            )
        )
        rendered_text = renderer.render(decision.payload).text
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
                RenderedAlertSummary(
                    symbol_id=symbol_id,
                    ticker="TEST",
                    alert_state="NEW",
                    rendered_text=rendered_text,
                )
            ],
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


def test_product_service_run_once_persists_and_sends(tmp_path, monkeypatch):
    class _Settings:
        database_url = "sqlite://"
        polygon_api_key = None
        polygon_base_url = "https://api.polygon.io"
        polygon_timeout_seconds = 5
        operator_state_db_path = str(tmp_path / "ops.db")
        telegram_enabled = True
        telegram_bot_token = "token"
        telegram_chat_id = "chat"
        polygon_universe_refresh_limit = 10
        universe_min_price = Decimal("5")
        universe_max_price = Decimal("50")
        universe_min_avg_volume_20d = Decimal("500000")
        universe_min_avg_dollar_volume_20d = Decimal("5000000")
        polygon_intraday_lookback_days = 30
        polygon_daily_lookback_days = 90
        phase2_history_window_bars = 20
        polygon_news_lookback_hours = 72
        polygon_news_limit = 25
        halt_status_mode = "fail_open"
        alert_cooldown_minutes = 60
        log_level = "INFO"

    state_store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = DoctrineProductApp(
        settings=_Settings(),
        state_store=state_store,
        sync_service=_StubSyncService(),
        telegram_transport=_StubTransport(),
        runner_pipeline_factory=_StubRunnerPipeline,
    )
    result = app.run_once()
    assert result.runner_result.run_status == "SUCCESS"
    assert result.transport_results[0].transport_status == "SENT"
    assert state_store.recent_alerts(limit=1, suppressed=False)[0]["telegram_status"] == "SENT"


def test_product_service_run_once_persists_micro_contract_and_web_reads_same_values(tmp_path):
    class _Settings:
        database_url = "sqlite://"
        polygon_api_key = None
        polygon_base_url = "https://api.polygon.io"
        polygon_timeout_seconds = 5
        operator_state_db_path = str(tmp_path / "ops.db")
        telegram_enabled = True
        telegram_bot_token = "token"
        telegram_chat_id = "chat"
        polygon_universe_refresh_limit = 10
        universe_min_price = Decimal("5")
        universe_max_price = Decimal("50")
        universe_min_avg_volume_20d = Decimal("500000")
        universe_min_avg_dollar_volume_20d = Decimal("5000000")
        polygon_intraday_lookback_days = 30
        polygon_daily_lookback_days = 90
        phase2_history_window_bars = 20
        polygon_news_lookback_hours = 72
        polygon_news_limit = 25
        halt_status_mode = "fail_open"
        alert_cooldown_minutes = 60
        log_level = "INFO"

    state_store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = DoctrineProductApp(
        settings=_Settings(),
        state_store=state_store,
        sync_service=_StubSyncService(),
        telegram_transport=_StubTransport(),
        runner_pipeline_factory=_StubRunnerPipeline,
    )

    result = app.run_once()

    persisted_alert = state_store.recent_alerts(limit=1, suppressed=False)[0]
    assert result.runner_result.run_status == "SUCCESS"
    assert persisted_alert["micro_state"] == "AVAILABLE_NOT_USED"
    assert persisted_alert["micro_present"] == 1
    assert persisted_alert["micro_trigger_state"] == "LTF_BULLISH_RECLAIM"
    assert persisted_alert["micro_used_for_confirmation"] == 0
    assert persisted_alert["signal_timestamp"] == "2026-03-11T10:15:00+00:00"
    assert persisted_alert["known_at"] == "2026-03-11T10:15:00+00:00"

    client = TestClient(app.create_operator_app())
    alerts_response = client.get("/api/alerts", params={"ticker": "TEST"})
    assert alerts_response.status_code == 200
    alert_payload = alerts_response.json()[0]
    assert alert_payload["micro_state"] == "AVAILABLE_NOT_USED"
    assert alert_payload["micro_present"] == 1
    assert alert_payload["micro_trigger_state"] == "LTF_BULLISH_RECLAIM"
    assert alert_payload["micro_used_for_confirmation"] == 0
    assert alert_payload["signal_timestamp"] == "2026-03-11T10:15:00+00:00"
    assert alert_payload["known_at"] == "2026-03-11T10:15:00+00:00"

    page = client.get("/")
    assert page.status_code == 200
    assert "AVAILABLE_NOT_USED" in page.text
    assert "LTF_BULLISH_RECLAIM" in page.text
    assert "Signal Time" in page.text
    assert "Known At" in page.text


def test_build_runner_config_requests_5m_micro() -> None:
    class _Settings:
        database_url = "sqlite://"
        polygon_api_key = None
        telegram_enabled = False
        telegram_bot_token = None
        telegram_chat_id = None
        polygon_base_url = "https://api.polygon.io"
        polygon_timeout_seconds = 5
        operator_state_db_path = ":memory:"
        polygon_universe_refresh_limit = 10
        alert_cooldown_minutes = 60

    app = DoctrineProductApp(
        settings=_Settings(),
        session_factory=object(),
        state_store=OperationalStateStore(":memory:"),
        sync_service=_StubSyncService(),
        telegram_transport=_StubTransport(),
        runner_pipeline_factory=_StubRunnerPipeline,
    )
    config = app.build_runner_config()
    assert config.timeframes.micro == "5M"
    assert config.require_micro_confirmation is False


def test_phase2_loader_requests_micro_when_runner_config_sets_5m(monkeypatch) -> None:
    requested_timeframes: list[str] = []

    class _SessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_load_frame_context(*, session, symbol_id, timeframe, history_window_bars):
        requested_timeframes.append(timeframe.value)
        return {"timeframe": timeframe.value}

    monkeypatch.setattr("doctrine_engine.product.adapters._load_frame_context", _fake_load_frame_context)

    loader = DbPhase2FeatureLoader(session_factory=lambda: _SessionContext(), history_window_bars=10)
    symbol = UniverseSymbolContext(
        symbol_id=uuid.uuid4(),
        ticker="SOFI",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("18.29"),
        universe_reason_codes=[],
        universe_known_at=datetime(2026, 3, 11, 23, 0, tzinfo=timezone.utc),
    )
    runner_input = RunnerInput(
        run_id=uuid.uuid4(),
        triggered_at=datetime(2026, 3, 11, 23, 0, tzinfo=timezone.utc),
        config=RunnerConfig(
            universe=UniverseSelectionConfig(max_symbols_per_run=None),
            timeframes=TimeframeConfig(micro="5M"),
        ),
    )

    result = loader.load(symbol, runner_input)

    assert requested_timeframes == ["4H", "1H", "15M", "5M"]
    assert result.micro == {"timeframe": "5M"}
