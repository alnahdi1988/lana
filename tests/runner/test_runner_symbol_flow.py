from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

from doctrine_engine.runner.models import RunnerConfig, RunnerInput, UniverseSelectionConfig, UniverseSymbolContext
from doctrine_engine.runner.pipeline import RunnerPipeline
sys.path.append(str(Path(__file__).resolve().parent))

from test_runner_pipeline_order import (
    EventRiskInputLoader,
    FakeAlertWorkflow,
    FakeEventRiskEngine,
    FakeRankingEngine,
    FakeRegimeEngine,
    FakeRenderer,
    FakeSignalEngine,
    FakeTradePlanEngine,
    MarketLoader,
    Phase2Loader,
    PriorAlertLoader,
    Recorder,
    RegimeInputLoader,
    UniverseLoader,
    make_alert_decision,
    make_benchmark_context,
    make_event_risk_input,
    make_event_risk_result,
    make_phase2_context,
    make_ranking_result,
    make_regime_input,
    make_regime_result,
    make_signal_result,
    make_symbol_context,
    make_trade_plan_result,
)


def _symbol() -> UniverseSymbolContext:
    return UniverseSymbolContext(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=["UNIVERSE_ELIGIBLE"],
        universe_known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
    )


def test_full_happy_path_symbol_produces_all_outputs() -> None:
    recorder = Recorder()
    symbol = _symbol()
    signal_result = make_signal_result(symbol)
    signal_id = uuid.uuid4()
    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=lambda config: FakeSignalEngine(recorder, signal_result),
        trade_plan_engine=FakeTradePlanEngine(recorder, make_trade_plan_result(signal_id, symbol)),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
        ranking_engine=FakeRankingEngine(recorder, make_ranking_result(signal_id, symbol)),
        alert_workflow_factory=lambda config: FakeAlertWorkflow(recorder, make_alert_decision(signal_id, symbol)),
        telegram_renderer=FakeRenderer(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                enable_ranking=True,
                enable_alert_workflow=True,
            ),
        )
    )
    assert result.run_status == "SUCCESS"
    assert result.generated_signals == 1
    assert result.generated_trade_plans == 1
    assert result.ranked_symbols == 1
    assert result.sendable_alerts == 1
    assert result.rendered_alerts == 1
    assert result.symbol_summaries[0].status == "SUCCESS"
    assert result.symbol_summaries[0].stage_reached == "RENDER_ALERT_TEXT"
    assert result.rendered_alert_texts[0].rendered_text == "rendered"


def test_none_signal_skips_downstream_stages_cleanly() -> None:
    recorder = Recorder()
    symbol = _symbol()
    signal_result = replace(make_signal_result(symbol), signal="NONE", grade="IGNORE")
    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=lambda config: FakeSignalEngine(recorder, signal_result),
        trade_plan_engine=FakeTradePlanEngine(recorder, make_trade_plan_result(uuid.uuid4(), symbol)),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
        ranking_engine=FakeRankingEngine(recorder, make_ranking_result(uuid.uuid4(), symbol)),
        alert_workflow_factory=lambda config: FakeAlertWorkflow(recorder, make_alert_decision(uuid.uuid4(), symbol)),
        telegram_renderer=FakeRenderer(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                enable_ranking=True,
                enable_alert_workflow=True,
            ),
        )
    )
    assert result.run_status == "SUCCESS"
    assert result.generated_signals == 0
    assert result.generated_trade_plans == 0
    assert result.ranked_symbols == 0
    assert result.sendable_alerts == 0
    assert result.rendered_alerts == 0
    assert result.symbol_summaries[0].status == "SKIPPED"
    assert result.symbol_summaries[0].stage_reached == "BUILD_SIGNAL"
    assert "BUILD_TRADE_PLAN" not in recorder.calls


def test_missing_persisted_phase2_context_skips_symbol() -> None:
    class MissingPhase2Loader:
        def load(self, symbol, runner_input):
            return None

    recorder = Recorder()
    symbol = _symbol()
    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=MissingPhase2Loader(),
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
