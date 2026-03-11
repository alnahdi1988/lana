from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

from doctrine_engine.alerts.models import AlertDecisionResult
from doctrine_engine.runner.models import RunnerConfig, RunnerInput, UniverseSelectionConfig, UniverseSymbolContext
from doctrine_engine.runner.pipeline import RunnerPipeline
sys.path.append(str(Path(__file__).resolve().parent))

from test_runner_pipeline_order import (
    EventRiskInputLoader,
    FakeAlertWorkflow,
    FakeEventRiskEngine,
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


def test_suppressed_alert_does_not_invoke_renderer() -> None:
    recorder = Recorder()
    symbol = _symbol()
    decision = make_alert_decision(uuid.uuid4(), symbol)
    decision = AlertDecisionResult(
        send=False,
        alert_state="SUPPRESSED",
        suppression_reason="GRADE_NOT_SENDABLE",
        priority=decision.priority,
        dedup_key=decision.dedup_key,
        family_key=decision.family_key,
        payload_fingerprint=decision.payload_fingerprint,
        payload=decision.payload,
        snapshot_request=None,
    )
    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=lambda config: FakeSignalEngine(recorder, make_signal_result(symbol)),
        trade_plan_engine=FakeTradePlanEngine(recorder, make_trade_plan_result(uuid.uuid4(), symbol)),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
        ranking_engine=FakeRegimeEngine(recorder, make_regime_result()),
        alert_workflow_factory=lambda config: FakeAlertWorkflow(recorder, decision),
        telegram_renderer=FakeRenderer(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                enable_alert_workflow=True,
                enable_ranking=False,
            ),
        )
    )
    assert result.rendered_alerts == 0
    assert "RENDER_ALERT_TEXT" not in recorder.calls


def test_ranking_failure_does_not_prevent_alert_workflow_or_render() -> None:
    recorder = Recorder()
    symbol = _symbol()

    class FailingRankingEngine:
        def evaluate(self, ranking_input):
            raise ValueError("ranking failed")

    pipeline = RunnerPipeline(
        universe_context_loader=UniverseLoader(recorder, symbol),
        market_data_loader=MarketLoader(recorder, make_symbol_context(symbol.symbol_id), make_benchmark_context()),
        phase2_feature_loader=Phase2Loader(recorder, make_phase2_context(symbol.symbol_id)),
        regime_external_input_loader=RegimeInputLoader(recorder, make_regime_input(symbol, make_benchmark_context())),
        event_risk_external_input_loader=EventRiskInputLoader(recorder, make_event_risk_input(symbol)),
        prior_alert_state_loader=PriorAlertLoader(recorder),
        signal_engine_factory=lambda config: FakeSignalEngine(recorder, make_signal_result(symbol)),
        trade_plan_engine=FakeTradePlanEngine(recorder, make_trade_plan_result(uuid.uuid4(), symbol)),
        regime_engine=FakeRegimeEngine(recorder, make_regime_result()),
        event_risk_engine=FakeEventRiskEngine(recorder, make_event_risk_result()),
        ranking_engine=FailingRankingEngine(),
        alert_workflow_factory=lambda config: FakeAlertWorkflow(recorder, make_alert_decision(uuid.uuid4(), symbol)),
        telegram_renderer=FakeRenderer(recorder),
    )
    result = pipeline.run(
        RunnerInput(
            run_id=uuid.uuid4(),
            triggered_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
            config=RunnerConfig(
                universe=UniverseSelectionConfig(max_symbols_per_run=None),
                enable_alert_workflow=True,
                enable_ranking=True,
            ),
        )
    )
    assert result.rendered_alerts == 1
    assert result.symbol_summaries[0].status == "SUCCESS"
    assert result.symbol_summaries[0].stage_reached == "RENDER_ALERT_TEXT"
    assert result.symbol_summaries[0].error_message == "ranking failed"
