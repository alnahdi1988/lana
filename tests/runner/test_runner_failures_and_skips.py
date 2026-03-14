from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

from doctrine_engine.runner.models import BenchmarkPhaseContext, RunnerConfig, RunnerInput, UniverseSelectionConfig, UniverseSymbolContext
from doctrine_engine.runner.pipeline import RunnerPipeline
sys.path.append(str(Path(__file__).resolve().parent))

from test_runner_pipeline_order import (
    EventRiskInputLoader,
    FakeEventRiskEngine,
    FakeRegimeEngine,
    FakeSignalEngine,
    FakeTradePlanEngine,
    MarketLoader,
    Phase2Loader,
    PriorAlertLoader,
    Recorder,
    RegimeInputLoader,
    UniverseLoader,
    make_benchmark_context,
    make_event_risk_input,
    make_event_risk_result,
    make_phase2_context,
    make_regime_input,
    make_regime_result,
    make_signal_result,
    make_symbol_context,
    make_trade_plan_result,
)


def _symbol(ticker: str = "TEST") -> UniverseSymbolContext:
    return UniverseSymbolContext(
        symbol_id=uuid.uuid4(),
        ticker=ticker,
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=["UNIVERSE_ELIGIBLE"],
        universe_known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
    )


def test_missing_required_benchmark_phase_context_hard_fails_run() -> None:
    recorder = Recorder()
    symbol = _symbol()

    class BrokenBenchmarkLoader(MarketLoader):
        def load_benchmark_context(self, runner_input):
            self.recorder.calls.append("LOAD_BENCHMARK_CONTEXT")
            return BenchmarkPhaseContext(market_indexes=make_benchmark_context().market_indexes[:2])

    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=BrokenBenchmarkLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(universe=UniverseSelectionConfig(max_symbols_per_run=None)),
        )
    )
    assert result.run_status == "FAILED"
    assert result.total_symbols == 0


def test_missing_required_timeframe_bars_skips_symbol() -> None:
    recorder = Recorder()
    symbol = _symbol()

    class MissingBarLoader(MarketLoader):
        def load_symbol_context(self, symbol, runner_input):
            self.recorder.calls.append("LOAD_SYMBOL_MARKET_CONTEXT")
            context = make_symbol_context(symbol.symbol_id)
            return context.__class__(
                htf_bar=context.htf_bar,
                mtf_bar=context.mtf_bar,
                ltf_bar=None,
                micro_bar=None,
            )

    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MissingBarLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(universe=UniverseSelectionConfig(max_symbols_per_run=None)),
        )
    )
    assert result.run_status == "SUCCESS"
    assert result.skipped_symbols == 1
    assert result.symbol_summaries[0].stage_reached == "LOAD_PHASE2_CONTEXT"


def test_external_read_retry_is_config_driven() -> None:
    recorder = Recorder()
    symbol = _symbol()

    class FlakyMarketLoader(MarketLoader):
        def __init__(self, recorder, symbol_context, benchmark_context) -> None:
            super().__init__(recorder, symbol_context, benchmark_context)
            self.attempts = 0

        def load_symbol_context(self, symbol, runner_input):
            self.attempts += 1
            self.recorder.calls.append("LOAD_SYMBOL_MARKET_CONTEXT")
            if self.attempts == 1:
                raise RuntimeError("transient")
            return self.symbol_context

    signal_result = replace(make_signal_result(symbol), signal="NONE", grade="IGNORE")
    flaky_loader = FlakyMarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context())
    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=flaky_loader,
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=lambda config: FakeSignalEngine(recorder, signal_result),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                external_read_retry_attempts=2,
                external_read_retry_backoff_ms=0,
            ),
        )
    )
    assert flaky_loader.attempts == 2
    assert result.run_status == "SUCCESS"


def test_trade_plan_failure_with_continue_on_error_yields_partial_success() -> None:
    recorder = Recorder()
    symbols = [_symbol("AAA"), _symbol("BBB")]

    class MultiUniverseLoader:
        def load(self, runner_input):
            return symbols

    class ConditionalPhase2Loader:
        def load(self, symbol, runner_input):
            return make_phase2_context(symbol.symbol_id)

    class ConditionalMarketLoader(MarketLoader):
        def load_symbol_context(self, symbol, runner_input):
            return make_symbol_context(symbol.symbol_id)

    class ConditionalSignalFactory:
        def __call__(self, config):
            class Engine:
                def evaluate(self_inner, signal_input):
                    return make_signal_result(
                        UniverseSymbolContext(
                            symbol_id=signal_input.symbol_id,
                            ticker=signal_input.ticker,
                            universe_snapshot_id=signal_input.universe_snapshot_id,
                            universe_eligible=signal_input.universe_eligible,
                            price_reference=signal_input.price_reference,
                            universe_reason_codes=signal_input.universe_reason_codes,
                            universe_known_at=signal_input.universe_known_at,
                        )
                    )

            return Engine()

    class ConditionalTradePlanEngine:
        def build_plan(self, trade_plan_input):
            if trade_plan_input.signal_result.ticker == "AAA":
                raise ValueError("bad plan")
            return make_trade_plan_result(trade_plan_input.signal_id, symbols[1])

    pipeline = RunnerPipeline(
        universe_context_loader=MultiUniverseLoader(),
        market_data_loader=ConditionalMarketLoader(recorder, make_symbol_context(symbols[0].symbol_id), make_benchmark_context()),
        phase2_feature_loader=ConditionalPhase2Loader(),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbols[0], make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbols[0])),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=ConditionalSignalFactory(),
        trade_plan_engine=ConditionalTradePlanEngine(),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                continue_on_symbol_error=True,
                enable_alert_workflow=False,
                enable_ranking=False,
            ),
        )
    )
    assert result.run_status == "PARTIAL_SUCCESS"
    assert result.failed_symbols == 1
    assert result.succeeded_symbols == 1


def test_non_fatal_trade_plan_geometry_error_skips_symbol() -> None:
    recorder = Recorder()
    symbol = _symbol("IREN")

    class GeometrySignalFactory:
        def __call__(self, config):
            class Engine:
                def evaluate(self_inner, signal_input):
                    return make_signal_result(
                        UniverseSymbolContext(
                            symbol_id=signal_input.symbol_id,
                            ticker=signal_input.ticker,
                            universe_snapshot_id=signal_input.universe_snapshot_id,
                            universe_eligible=signal_input.universe_eligible,
                            price_reference=signal_input.price_reference,
                            universe_reason_codes=signal_input.universe_reason_codes,
                            universe_known_at=signal_input.universe_known_at,
                        )
                    )

            return Engine()

    class GeometryTradePlanEngine:
        def build_plan(self, trade_plan_input):
            raise ValueError("Invalidation anchor cannot fall inside the entry zone.")

    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=GeometrySignalFactory(),
        trade_plan_engine=GeometryTradePlanEngine(),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                enable_alert_workflow=False,
                enable_ranking=False,
            ),
        )
    )
    assert result.run_status == "SUCCESS"
    assert result.failed_symbols == 0
    assert result.skipped_symbols == 1
    assert result.symbol_summaries[0].status == "SKIPPED"
    assert result.symbol_summaries[0].stage_reached == "BUILD_TRADE_PLAN"
    assert result.symbol_summaries[0].error_message == "Invalidation anchor cannot fall inside the entry zone."
