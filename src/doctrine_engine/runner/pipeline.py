from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Protocol

from doctrine_engine.alerts.models import AlertWorkflowInput, SnapshotRequestConfig
from doctrine_engine.alerts.telegram_renderer import TelegramRenderer
from doctrine_engine.alerts.workflow import AlertWorkflow, AlertWorkflowConfig
from doctrine_engine.engines.models import (
    SignalEngineInput,
    SignalEventRiskInput,
    SignalFrameInput,
    SignalRegimeInput,
    SignalSectorContextInput,
    TradePlanEngineInput,
)
from doctrine_engine.engines.signal_engine import SignalEngine, SignalEngineConfig
from doctrine_engine.engines.trade_plan_engine import TradePlanEngine
from doctrine_engine.event_risk.engine import EventRiskEngine
from doctrine_engine.ranking.engine import RankingEngine
from doctrine_engine.ranking.models import RankingEngineInput
from doctrine_engine.regime.engine import RegimeEngine
from doctrine_engine.runner.adapters import (
    EventRiskExternalInputLoader,
    MarketDataLoader,
    Phase2FeatureLoader,
    PriorAlertStateLoader,
    RegimeExternalInputLoader,
    UniverseContextLoader,
)
from doctrine_engine.runner.models import (
    RenderedAlertSummary,
    RunnerConfig,
    RunnerInput,
    RunnerResult,
    STAGE_ORDER,
    SymbolRunSummary,
    UniverseSymbolContext,
)

LOGGER = logging.getLogger(__name__)

NON_FATAL_TRADE_PLAN_ERRORS = {
    "No structural confirmation level exists above the entry zone.",
    "Invalidation anchor cannot fall inside the entry zone.",
    "No structural invalidation anchor exists.",
    "No structural TP1 candidate exists.",
    "No structural TP2 candidate exists.",
}


class SignalEvaluator(Protocol):
    def evaluate(self, signal_input: SignalEngineInput): ...


class TradePlanBuilder(Protocol):
    def build_plan(self, trade_plan_input: TradePlanEngineInput): ...


class RegimeEvaluator(Protocol):
    def evaluate(self, regime_input): ...


class EventRiskEvaluator(Protocol):
    def evaluate(self, event_risk_input): ...


class RankingEvaluator(Protocol):
    def evaluate(self, ranking_input): ...


class AlertWorkflowEvaluator(Protocol):
    def evaluate(self, workflow_input: AlertWorkflowInput): ...


class TelegramRendererProtocol(Protocol):
    def render(self, payload): ...


class RunnerPipeline:
    def __init__(
        self,
        *,
        universe_context_loader: UniverseContextLoader,
        market_data_loader: MarketDataLoader,
        phase2_feature_loader: Phase2FeatureLoader,
        regime_external_input_loader: RegimeExternalInputLoader,
        event_risk_external_input_loader: EventRiskExternalInputLoader,
        prior_alert_state_loader: PriorAlertStateLoader,
        signal_engine_factory: Callable[[RunnerConfig], SignalEvaluator] | None = None,
        trade_plan_engine: TradePlanBuilder | None = None,
        regime_engine: RegimeEvaluator | None = None,
        event_risk_engine: EventRiskEvaluator | None = None,
        ranking_engine: RankingEvaluator | None = None,
        alert_workflow_factory: Callable[[RunnerConfig], AlertWorkflowEvaluator] | None = None,
        telegram_renderer: TelegramRendererProtocol | None = None,
    ) -> None:
        self.universe_context_loader = universe_context_loader
        self.market_data_loader = market_data_loader
        self.phase2_feature_loader = phase2_feature_loader
        self.regime_external_input_loader = regime_external_input_loader
        self.event_risk_external_input_loader = event_risk_external_input_loader
        self.prior_alert_state_loader = prior_alert_state_loader
        self.signal_engine_factory = signal_engine_factory or self._default_signal_engine_factory
        self.trade_plan_engine = trade_plan_engine or TradePlanEngine()
        self.regime_engine = regime_engine or RegimeEngine()
        self.event_risk_engine = event_risk_engine or EventRiskEngine()
        self.ranking_engine = ranking_engine or RankingEngine()
        self.alert_workflow_factory = alert_workflow_factory or self._default_alert_workflow_factory
        self.telegram_renderer = telegram_renderer or TelegramRenderer()

    def run(self, runner_input: RunnerInput) -> RunnerResult:
        started_at = datetime.now(timezone.utc)
        self._validate_runner_input(runner_input)

        LOGGER.info("%s", STAGE_ORDER[0])
        try:
            universe_symbols = self._retry_external_read(
                runner_input=runner_input,
                func=lambda: self.universe_context_loader.load(runner_input),
                context="load universe context",
            )
        except Exception as exc:  # pragma: no cover - exercised via tests
            return self._failed_run_result(runner_input, started_at, str(exc))

        universe_symbols = self._filter_symbols(universe_symbols, runner_input.config)
        if not universe_symbols:
            return self._failed_run_result(runner_input, started_at, "No symbols available after universe load.")

        LOGGER.info("%s", STAGE_ORDER[1])
        try:
            benchmark_context = self._retry_external_read(
                runner_input=runner_input,
                func=lambda: self.market_data_loader.load_benchmark_context(runner_input),
                context="load benchmark phase context",
            )
        except Exception as exc:
            return self._failed_run_result(runner_input, started_at, str(exc))

        benchmark_tickers = {index.ticker for index in benchmark_context.market_indexes}
        if benchmark_tickers != {"SPY", "QQQ", "IWM"}:
            return self._failed_run_result(
                runner_input,
                started_at,
                "Benchmark phase context must include exactly SPY, QQQ, and IWM.",
            )

        signal_engine = self.signal_engine_factory(runner_input.config)
        alert_workflow = self.alert_workflow_factory(runner_input.config)

        symbol_summaries: list[SymbolRunSummary] = []
        rendered_alert_texts: list[RenderedAlertSummary] = []
        succeeded_symbols = 0
        skipped_symbols = 0
        failed_symbols = 0
        generated_signals = 0
        generated_trade_plans = 0
        ranked_symbols = 0
        sendable_alerts = 0
        rendered_alerts = 0

        for symbol in universe_symbols:
            summary, counters, rendered = self._process_symbol(
                runner_input=runner_input,
                symbol=symbol,
                benchmark_context=benchmark_context,
                signal_engine=signal_engine,
                alert_workflow=alert_workflow,
            )
            symbol_summaries.append(summary)
            rendered_alert_texts.extend(rendered)
            succeeded_symbols += counters["succeeded"]
            skipped_symbols += counters["skipped"]
            failed_symbols += counters["failed"]
            generated_signals += counters["generated_signals"]
            generated_trade_plans += counters["generated_trade_plans"]
            ranked_symbols += counters["ranked_symbols"]
            sendable_alerts += counters["sendable_alerts"]
            rendered_alerts += counters["rendered_alerts"]

            if runner_input.config.fail_fast and summary.status == "FAILED":
                break
            if failed_symbols >= runner_input.config.max_symbol_failures_before_abort:
                break

        finished_at = datetime.now(timezone.utc)
        run_status = self._run_status(
            total_symbols=len(universe_symbols),
            succeeded_symbols=succeeded_symbols,
            skipped_symbols=skipped_symbols,
            failed_symbols=failed_symbols,
        )
        LOGGER.info("%s", STAGE_ORDER[-1])
        return RunnerResult(
            run_id=runner_input.run_id,
            started_at=started_at,
            finished_at=finished_at,
            run_status=run_status,
            total_symbols=len(universe_symbols),
            succeeded_symbols=succeeded_symbols,
            skipped_symbols=skipped_symbols,
            failed_symbols=failed_symbols,
            generated_signals=generated_signals,
            generated_trade_plans=generated_trade_plans,
            ranked_symbols=ranked_symbols,
            sendable_alerts=sendable_alerts,
            rendered_alerts=rendered_alerts,
            rendered_alert_texts=rendered_alert_texts,
            symbol_summaries=symbol_summaries,
        )

    def _process_symbol(
        self,
        *,
        runner_input: RunnerInput,
        symbol: UniverseSymbolContext,
        benchmark_context,
        signal_engine: SignalEvaluator,
        alert_workflow: AlertWorkflowEvaluator,
    ) -> tuple[SymbolRunSummary, dict[str, int], list[RenderedAlertSummary]]:
        counters = {
            "succeeded": 0,
            "skipped": 0,
            "failed": 0,
            "generated_signals": 0,
            "generated_trade_plans": 0,
            "ranked_symbols": 0,
            "sendable_alerts": 0,
            "rendered_alerts": 0,
        }
        rendered: list[RenderedAlertSummary] = []

        phase2_context = self.phase2_feature_loader.load(symbol, runner_input)
        if phase2_context is None:
            counters["skipped"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="SKIPPED",
                    stage_reached="LOAD_PHASE2_CONTEXT",
                    signal=None,
                    ranking_tier=None,
                    alert_state=None,
                    error_message="Persisted Phase 2 context missing.",
                ),
                counters,
                rendered,
            )

        try:
            symbol_market_context = self._retry_external_read(
                runner_input=runner_input,
                func=lambda: self.market_data_loader.load_symbol_context(symbol, runner_input),
                context=f"load symbol market context for {symbol.ticker}",
            )
        except Exception as exc:
            counters["failed"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="FAILED",
                    stage_reached="LOAD_PHASE2_CONTEXT",
                    signal=None,
                    ranking_tier=None,
                    alert_state=None,
                    error_message=str(exc),
                ),
                counters,
                rendered,
            )

        if not self._has_required_symbol_bars(symbol_market_context, runner_input.config):
            counters["skipped"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="SKIPPED",
                    stage_reached="LOAD_PHASE2_CONTEXT",
                    signal=None,
                    ranking_tier=None,
                    alert_state=None,
                    error_message="Required timeframe bars missing.",
                ),
                counters,
                rendered,
            )

        try:
            LOGGER.info("%s", "BUILD_REGIME")
            regime_input = self._retry_external_read(
                runner_input=runner_input,
                func=lambda: self.regime_external_input_loader.load(symbol, benchmark_context, runner_input),
                context=f"load regime external inputs for {symbol.ticker}",
            )
            regime_result = self.regime_engine.evaluate(regime_input)

            LOGGER.info("%s", "BUILD_EVENT_RISK")
            event_risk_input = self._retry_external_read(
                runner_input=runner_input,
                func=lambda: self.event_risk_external_input_loader.load(
                    symbol,
                    symbol_market_context.ltf_bar.bar_timestamp,
                    symbol_market_context.ltf_bar.known_at,
                    runner_input,
                ),
                context=f"load event-risk external inputs for {symbol.ticker}",
            )
            event_risk_result = self.event_risk_engine.evaluate(event_risk_input)

            LOGGER.info("%s", "BUILD_SIGNAL")
            signal_input = self._build_signal_input(
                symbol=symbol,
                phase2_context=phase2_context,
                symbol_market_context=symbol_market_context,
                regime_input=regime_input,
                regime_result=regime_result,
                event_risk_result=event_risk_result,
            )
            signal_result = signal_engine.evaluate(signal_input)
        except Exception as exc:
            counters["failed"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="FAILED",
                    stage_reached="BUILD_SIGNAL",
                    signal=None,
                    ranking_tier=None,
                    alert_state=None,
                    error_message=str(exc),
                ),
                counters,
                rendered,
            )

        if signal_result.signal != "LONG":
            counters["skipped"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="SKIPPED",
                    stage_reached="BUILD_SIGNAL",
                    signal=signal_result.signal,
                    ranking_tier=None,
                    alert_state=None,
                    error_message=None,
                ),
                counters,
                rendered,
            )

        counters["generated_signals"] = 1
        signal_id = uuid.uuid4()

        try:
            LOGGER.info("%s", "BUILD_TRADE_PLAN")
            trade_plan_result = self.trade_plan_engine.build_plan(
                TradePlanEngineInput(
                    signal_id=signal_id,
                    signal_result=signal_result,
                    signal_source=signal_input,
                )
            )
        except Exception as exc:
            if self._is_non_fatal_trade_plan_error(exc):
                counters["skipped"] = 1
                return (
                    SymbolRunSummary(
                        symbol_id=symbol.symbol_id,
                        ticker=symbol.ticker,
                        status="SKIPPED",
                        stage_reached="BUILD_TRADE_PLAN",
                        signal=signal_result.signal,
                        ranking_tier=None,
                        alert_state=None,
                        error_message=str(exc),
                    ),
                    counters,
                    rendered,
                )
            counters["failed"] = 1
            return (
                SymbolRunSummary(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    status="FAILED",
                    stage_reached="BUILD_TRADE_PLAN",
                    signal=signal_result.signal,
                    ranking_tier=None,
                    alert_state=None,
                    error_message=str(exc),
                ),
                counters,
                rendered,
            )

        counters["generated_trade_plans"] = 1
        ranking_tier = None
        ranking_error = None

        if runner_input.config.enable_ranking:
            try:
                LOGGER.info("%s", "BUILD_RANKING")
                ranking_result = self.ranking_engine.evaluate(
                    RankingEngineInput(
                        signal_id=signal_id,
                        signal_result=signal_result,
                        trade_plan_result=trade_plan_result,
                        regime_result=regime_result,
                        event_risk_result=event_risk_result,
                    )
                )
                ranking_tier = ranking_result.ranking_tier
                counters["ranked_symbols"] = 1
            except Exception as exc:
                ranking_error = str(exc)

        alert_state = None
        stage_reached = "BUILD_TRADE_PLAN"
        error_message = ranking_error

        if runner_input.config.enable_alert_workflow:
            try:
                LOGGER.info("%s", "BUILD_ALERT_DECISION")
                prior_alert_state = self._retry_external_read(
                    runner_input=runner_input,
                    func=lambda: self.prior_alert_state_loader.load(
                        symbol.symbol_id,
                        signal_result.setup_state,
                        trade_plan_result.entry_type,
                    ),
                    context=f"load prior alert state for {symbol.ticker}",
                )
                workflow_result = alert_workflow.evaluate(
                    AlertWorkflowInput(
                        signal_id=signal_id,
                        signal_result=signal_result,
                        trade_plan_result=trade_plan_result,
                        prior_alert_state=prior_alert_state,
                        snapshot_request_config=(
                            SnapshotRequestConfig(
                                enabled=True,
                                output_dir="",
                            )
                            if runner_input.config.enable_snapshot_requests
                            else None
                        ),
                    )
                )
                alert_state = workflow_result.alert_state
                stage_reached = "BUILD_ALERT_DECISION"
                if workflow_result.send:
                    counters["sendable_alerts"] = 1
                    LOGGER.info("%s", "RENDER_ALERT_TEXT")
                    rendered_result = self.telegram_renderer.render(workflow_result.payload)
                    rendered.append(
                        RenderedAlertSummary(
                            symbol_id=symbol.symbol_id,
                            ticker=symbol.ticker,
                            alert_state=workflow_result.alert_state,
                            rendered_text=rendered_result.text,
                        )
                    )
                    counters["rendered_alerts"] = 1
                    stage_reached = "RENDER_ALERT_TEXT"
            except Exception as exc:
                counters["failed"] = 1
                return (
                    SymbolRunSummary(
                        symbol_id=symbol.symbol_id,
                        ticker=symbol.ticker,
                        status="FAILED",
                        stage_reached=stage_reached if stage_reached != "BUILD_TRADE_PLAN" else "BUILD_ALERT_DECISION",
                        signal=signal_result.signal,
                        ranking_tier=ranking_tier,
                        alert_state=alert_state,
                        error_message=str(exc),
                    ),
                    counters,
                    rendered,
                )

        counters["succeeded"] = 1
        return (
            SymbolRunSummary(
                symbol_id=symbol.symbol_id,
                ticker=symbol.ticker,
                status="SUCCESS",
                stage_reached=stage_reached,
                signal=signal_result.signal,
                ranking_tier=ranking_tier,
                alert_state=alert_state,
                error_message=error_message,
            ),
            counters,
            rendered,
        )

    def _build_signal_input(
        self,
        *,
        symbol: UniverseSymbolContext,
        phase2_context,
        symbol_market_context,
        regime_input,
        regime_result,
        event_risk_result,
    ) -> SignalEngineInput:
        return SignalEngineInput(
            symbol_id=symbol.symbol_id,
            ticker=symbol.ticker,
            universe_snapshot_id=symbol.universe_snapshot_id,
            universe_eligible=symbol.universe_eligible,
            price_reference=symbol.price_reference,
            universe_reason_codes=list(symbol.universe_reason_codes),
            universe_known_at=symbol.universe_known_at,
            htf=self._build_frame_input("4H", symbol_market_context.htf_bar, phase2_context.htf),
            mtf=self._build_frame_input("1H", symbol_market_context.mtf_bar, phase2_context.mtf),
            ltf=self._build_frame_input("15M", symbol_market_context.ltf_bar, phase2_context.ltf),
            micro=(
                self._build_frame_input("5M", symbol_market_context.micro_bar, phase2_context.micro)
                if symbol_market_context.micro_bar is not None and phase2_context.micro is not None
                else None
            ),
            regime=SignalRegimeInput(
                market_regime=regime_result.market_regime,
                sector_regime=regime_result.sector_regime,
                market_permission_score=regime_result.market_permission_score,
                sector_permission_score=regime_result.sector_permission_score,
                allows_longs=regime_result.allows_longs,
                coverage_complete=regime_result.coverage_complete,
                reason_codes=list(regime_result.reason_codes),
                known_at=regime_result.known_at,
            ),
            event_risk=SignalEventRiskInput(
                event_risk_class=event_risk_result.event_risk_class,
                blocked=event_risk_result.blocked,
                coverage_complete=event_risk_result.coverage_complete,
                soft_penalty=event_risk_result.soft_penalty,
                reason_codes=list(event_risk_result.reason_codes),
                known_at=event_risk_result.known_at,
            ),
            sector_context=SignalSectorContextInput(
                sector_strength=self._sector_strength(regime_result.sector_regime),
                relative_strength_score=regime_input.stock_relative.relative_strength_vs_sector,
                reason_codes=list(regime_result.reason_codes),
                known_at=regime_result.known_at,
            ),
        )

    @staticmethod
    def _build_frame_input(timeframe: str, latest_bar, frame_context) -> SignalFrameInput:
        return SignalFrameInput(
            timeframe=timeframe,
            latest_bar=latest_bar,
            structure=frame_context.structure,
            structure_history=list(frame_context.structure_history),
            zone=frame_context.zone,
            pattern=frame_context.pattern,
        )

    @staticmethod
    def _sector_strength(sector_regime: str) -> str:
        return {
            "SECTOR_STRONG": "STRONG",
            "SECTOR_NEUTRAL": "NEUTRAL",
            "SECTOR_WEAK": "WEAK",
        }[sector_regime]

    def _retry_external_read(self, *, runner_input: RunnerInput, func, context: str):
        attempts = runner_input.config.external_read_retry_attempts
        backoff = runner_input.config.external_read_retry_backoff_ms / 1000.0
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except Exception as exc:  # pragma: no cover - branch checked by tests through outcomes
                last_error = exc
                if attempt == attempts:
                    break
                if backoff > 0:
                    time.sleep(backoff)
        assert last_error is not None
        raise RuntimeError(f"{context} failed after {attempts} attempt(s): {last_error}") from last_error

    @staticmethod
    def _has_required_symbol_bars(symbol_market_context, config: RunnerConfig) -> bool:
        if (
            symbol_market_context.htf_bar is None
            or symbol_market_context.mtf_bar is None
            or symbol_market_context.ltf_bar is None
        ):
            return False
        if config.require_micro_confirmation and symbol_market_context.micro_bar is None:
            return False
        return True

    @staticmethod
    def _filter_symbols(symbols: list[UniverseSymbolContext], config: RunnerConfig) -> list[UniverseSymbolContext]:
        filtered = [
            symbol
            for symbol in symbols
            if (not config.universe.include_tickers or symbol.ticker in config.universe.include_tickers)
            and symbol.ticker not in config.universe.exclude_tickers
        ]
        if config.universe.max_symbols_per_run is not None:
            return filtered[: config.universe.max_symbols_per_run]
        return filtered

    @staticmethod
    def _run_status(
        *,
        total_symbols: int,
        succeeded_symbols: int,
        skipped_symbols: int,
        failed_symbols: int,
    ) -> str:
        if total_symbols == 0:
            return "FAILED"
        if failed_symbols == 0:
            return "SUCCESS"
        return "PARTIAL_SUCCESS"

    @staticmethod
    def _is_non_fatal_trade_plan_error(exc: Exception) -> bool:
        return isinstance(exc, ValueError) and str(exc) in NON_FATAL_TRADE_PLAN_ERRORS

    @staticmethod
    def _failed_run_result(runner_input: RunnerInput, started_at: datetime, error_message: str) -> RunnerResult:
        finished_at = datetime.now(timezone.utc)
        return RunnerResult(
            run_id=runner_input.run_id,
            started_at=started_at,
            finished_at=finished_at,
            run_status="FAILED",
            total_symbols=0,
            succeeded_symbols=0,
            skipped_symbols=0,
            failed_symbols=0,
            generated_signals=0,
            generated_trade_plans=0,
            ranked_symbols=0,
            sendable_alerts=0,
            rendered_alerts=0,
            rendered_alert_texts=[],
            symbol_summaries=[],
        )

    @staticmethod
    def _validate_runner_input(runner_input: RunnerInput) -> None:
        if runner_input.config.external_read_retry_attempts < 1:
            raise ValueError("external_read_retry_attempts must be at least 1.")
        if runner_input.config.max_symbol_failures_before_abort < 1:
            raise ValueError("max_symbol_failures_before_abort must be at least 1.")

    @staticmethod
    def _default_signal_engine_factory(config: RunnerConfig) -> SignalEvaluator:
        return SignalEngine(
            SignalEngineConfig(
                require_micro_confirmation=config.require_micro_confirmation,
                micro_context_requested=(
                    config.require_micro_confirmation or config.timeframes.micro is not None
                ),
            )
        )

    @staticmethod
    def _default_alert_workflow_factory(config: RunnerConfig) -> AlertWorkflowEvaluator:
        return AlertWorkflow(AlertWorkflowConfig(cooldown_minutes=config.alert_cooldown_minutes))
