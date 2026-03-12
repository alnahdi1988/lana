from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.alerts.models import AlertDecisionPayload, AlertDecisionResult, AlertWorkflowInput
from doctrine_engine.alerts.telegram_renderer import TelegramRenderer
from doctrine_engine.alerts.workflow import AlertWorkflow, AlertWorkflowConfig
from doctrine_engine.config.settings import Settings, get_settings
from doctrine_engine.product.adapters import (
    ConfiguredHaltStatusProvider,
    DbMarketDataLoader,
    DbPhase2FeatureLoader,
    DbRegimeExternalInputLoader,
    DbUniverseContextLoader,
    PolygonEventRiskInputLoader,
    SqlitePriorAlertStateLoader,
)
from doctrine_engine.product.clients import PolygonClient, TelegramSendResult, TelegramTransport
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.product.sync import PolygonSyncService, SyncResult
from doctrine_engine.product.web import create_operator_app
from doctrine_engine.runner.models import (
    RunnerConfig,
    RunnerInput,
    RunnerResult,
    TimeframeConfig,
    UniverseSelectionConfig,
)
from doctrine_engine.runner.pipeline import RunnerPipeline

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AlertTransportSummary:
    signal_id: uuid.UUID
    symbol_id: uuid.UUID
    ticker: str
    alert_state: str
    transport_status: str
    transport_error: str | None
    message_id: str | None


@dataclass(frozen=True, slots=True)
class ProductRunResult:
    sync_result: SyncResult
    runner_result: RunnerResult
    transport_results: list[AlertTransportSummary]


@dataclass(frozen=True, slots=True)
class CapturedAlertDecision:
    signal_id: uuid.UUID
    workflow_input: AlertWorkflowInput
    decision_result: AlertDecisionResult


class RecordingAlertWorkflow:
    def __init__(self, inner: AlertWorkflow) -> None:
        self.inner = inner
        self.records: list[CapturedAlertDecision] = []

    def evaluate(self, workflow_input: AlertWorkflowInput) -> AlertDecisionResult:
        result = self.inner.evaluate(workflow_input)
        self.records.append(
            CapturedAlertDecision(
                signal_id=workflow_input.signal_id,
                workflow_input=workflow_input,
                decision_result=result,
            )
        )
        return result


class RecordingTelegramRenderer:
    def __init__(self, inner: TelegramRenderer) -> None:
        self.inner = inner
        self.rendered_text_by_fingerprint: dict[str, str] = {}

    def render(self, payload: AlertDecisionPayload):
        result = self.inner.render(payload)
        self.rendered_text_by_fingerprint[_payload_fingerprint(payload)] = result.text
        return result


class DoctrineProductApp:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] | None = None,
        state_store: OperationalStateStore | None = None,
        polygon_client: PolygonClient | None = None,
        telegram_transport: TelegramTransport | None = None,
        sync_service: PolygonSyncService | None = None,
        runner_pipeline_factory: Callable[..., RunnerPipeline] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if session_factory is None:
            engine = create_engine(self.settings.database_url, future=True)
            session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        self.session_factory = session_factory
        self.state_store = state_store or OperationalStateStore(self.settings.operator_state_db_path)
        self.polygon_client = polygon_client
        if self.polygon_client is None and self.settings.polygon_api_key:
            self.polygon_client = PolygonClient(
                api_key=self.settings.polygon_api_key,
                base_url=self.settings.polygon_base_url,
                timeout_seconds=self.settings.polygon_timeout_seconds,
            )
        self.telegram_transport = telegram_transport or TelegramTransport(
            enabled=self.settings.telegram_enabled,
            bot_token=self.settings.telegram_bot_token,
            chat_id=self.settings.telegram_chat_id,
            timeout_seconds=self.settings.polygon_timeout_seconds,
        )
        self.sync_service = sync_service
        if self.sync_service is None and self.polygon_client is not None:
            self.sync_service = PolygonSyncService(
                session_factory=self.session_factory,
                polygon_client=self.polygon_client,
                universe_refresh_limit=self.settings.polygon_universe_refresh_limit,
                min_price=self.settings.universe_min_price,
                max_price=self.settings.universe_max_price,
                min_avg_volume_20d=self.settings.universe_min_avg_volume_20d,
                min_avg_dollar_volume_20d=self.settings.universe_min_avg_dollar_volume_20d,
                intraday_lookback_days=self.settings.polygon_intraday_lookback_days,
                daily_lookback_days=self.settings.polygon_daily_lookback_days,
                history_window_bars=self.settings.phase2_history_window_bars,
            )
        self.runner_pipeline_factory = runner_pipeline_factory or RunnerPipeline

    def build_runner_config(self) -> RunnerConfig:
        return RunnerConfig(
            run_mode="ONCE",
            universe=UniverseSelectionConfig(max_symbols_per_run=self.settings.polygon_universe_refresh_limit),
            timeframes=TimeframeConfig(micro="5M"),
            require_micro_confirmation=False,
            enable_ranking=True,
            enable_alert_workflow=True,
            enable_snapshot_requests=False,
            alert_cooldown_minutes=self.settings.alert_cooldown_minutes,
        )

    def run_once(self, runner_config: RunnerConfig | None = None) -> ProductRunResult:
        if self.sync_service is None:
            raise ValueError("Polygon API configuration is required to run the product pipeline.")
        config = runner_config or self.build_runner_config()
        LOGGER.info("Starting product sync.")
        sync_result = self.sync_service.prepare_run(config)
        LOGGER.info("Sync completed. snapshot_id=%s synced_tickers=%s errors=%s", sync_result.snapshot_id, len(sync_result.synced_tickers), len(sync_result.errors))

        if self.polygon_client is None and self.runner_pipeline_factory is RunnerPipeline:
            raise ValueError("Polygon API configuration is required to build the default runner pipeline.")
        workflow_wrapper = RecordingAlertWorkflow(AlertWorkflow(AlertWorkflowConfig(cooldown_minutes=config.alert_cooldown_minutes)))
        renderer_wrapper = RecordingTelegramRenderer(TelegramRenderer())
        runner = self.runner_pipeline_factory(
            universe_context_loader=DbUniverseContextLoader(self.session_factory),
            market_data_loader=DbMarketDataLoader(self.session_factory, self.settings.phase2_history_window_bars),
            phase2_feature_loader=DbPhase2FeatureLoader(self.session_factory, self.settings.phase2_history_window_bars),
            regime_external_input_loader=DbRegimeExternalInputLoader(self.session_factory, self.settings.phase2_history_window_bars),
            event_risk_external_input_loader=PolygonEventRiskInputLoader(
                polygon_client=self.polygon_client,
                news_lookback_hours=self.settings.polygon_news_lookback_hours,
                news_limit=self.settings.polygon_news_limit,
                halt_status_provider=ConfiguredHaltStatusProvider(self.settings.halt_status_mode),
            ),
            prior_alert_state_loader=SqlitePriorAlertStateLoader(self.state_store),
            alert_workflow_factory=lambda _config: workflow_wrapper,
            telegram_renderer=renderer_wrapper,
        )
        runner_input = RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime.now(timezone.utc),
            config=config,
        )
        runner_result = runner.run(runner_input)

        transport_results: list[AlertTransportSummary] = []
        telegram_sent = 0
        telegram_failed = 0
        for sync_error in sync_result.errors:
            self.state_store.record_error(
                run_id=runner_result.run_id,
                symbol_id=None,
                ticker=None,
                stage="SYNC_POLYGON",
                error_message=sync_error,
            )

        for record in workflow_wrapper.records:
            payload = record.decision_result.payload
            fingerprint = record.decision_result.payload_fingerprint
            rendered_text = renderer_wrapper.rendered_text_by_fingerprint.get(fingerprint)
            if record.decision_result.send:
                if rendered_text is None:
                    rendered_text = TelegramRenderer().render(payload).text
                transport_result = self.telegram_transport.send_message(rendered_text)
            else:
                transport_result = TelegramSendResult(
                    status="NOT_SENT",
                    message_id=None,
                    error_message=record.decision_result.suppression_reason,
                    sent_at=None,
                )
            if transport_result.status == "SENT":
                telegram_sent += 1
            elif transport_result.status == "FAILED":
                telegram_failed += 1
            self.state_store.record_alert_event(
                run_id=runner_result.run_id,
                signal_id=record.signal_id,
                decision_result=record.decision_result,
                rendered_text=rendered_text,
                transport_result=transport_result,
            )
            transport_results.append(
                AlertTransportSummary(
                    signal_id=record.signal_id,
                    symbol_id=payload.symbol_id,
                    ticker=payload.ticker,
                    alert_state=record.decision_result.alert_state,
                    transport_status=transport_result.status,
                    transport_error=transport_result.error_message,
                    message_id=transport_result.message_id,
                )
            )

        self.state_store.record_run(
            runner_result=runner_result,
            symbol_summaries=runner_result.symbol_summaries,
            telegram_sent=telegram_sent,
            telegram_failed=telegram_failed,
        )
        return ProductRunResult(
            sync_result=sync_result,
            runner_result=runner_result,
            transport_results=transport_results,
        )

    def run_forever(self, *, interval_seconds: int, runner_config: RunnerConfig | None = None) -> None:
        LOGGER.info("Starting continuous runner. interval_seconds=%s", interval_seconds)
        while True:
            try:
                result = self.run_once(runner_config=runner_config)
                LOGGER.info(
                    "Run completed. status=%s symbols=%s alerts=%s telegram_sent=%s telegram_failed=%s",
                    result.runner_result.run_status,
                    result.runner_result.total_symbols,
                    result.runner_result.sendable_alerts,
                    sum(1 for item in result.transport_results if item.transport_status == "SENT"),
                    sum(1 for item in result.transport_results if item.transport_status == "FAILED"),
                )
            except KeyboardInterrupt:  # pragma: no cover - manual operational path
                LOGGER.info("Continuous runner stopped.")
                return
            except Exception:  # pragma: no cover - manual operational path
                LOGGER.exception("Continuous runner iteration failed.")
            time.sleep(interval_seconds)

    def create_operator_app(self):
        return create_operator_app(self.state_store)


def _payload_fingerprint(payload: AlertDecisionPayload) -> str:
    parts = (
        payload.ticker,
        payload.signal,
        payload.grade,
        payload.setup_state,
        payload.entry_type,
        _decimal_text(payload.entry_zone_low),
        _decimal_text(payload.entry_zone_high),
        _decimal_text(payload.confirmation_level),
        _decimal_text(payload.invalidation_level),
        _decimal_text(payload.tp1),
        _decimal_text(payload.tp2),
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


__all__ = [
    "AlertTransportSummary",
    "DoctrineProductApp",
    "ProductRunResult",
]
