from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.alerts.models import AlertDecisionPayload, AlertDecisionResult
from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    SignalEngineResult,
    StructureEngineResult,
    StructureReferenceLevels,
    TradePlanEngineResult,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.event_risk.models import EventRiskEngineInput, EventRiskEngineResult
from doctrine_engine.regime.models import (
    BreadthInput,
    RegimeEngineInput,
    RegimeEngineResult,
    RegimeIndexInput,
    SectorRegimeInput,
    StockRelativeRegimeInput,
    VolatilityInput,
)
from doctrine_engine.runner.models import (
    BenchmarkPhaseContext,
    PersistedFramePhase2Context,
    PersistedPhase2Context,
    RunnerConfig,
    RunnerInput,
    SymbolMarketContext,
    UniverseSelectionConfig,
    UniverseSymbolContext,
)
from doctrine_engine.runner.pipeline import RunnerPipeline


def make_bar(symbol_id: uuid.UUID, timeframe: Timeframe, hour: int) -> EngineBar:
    ts = datetime(2026, 3, 11, hour, 0, tzinfo=timezone.utc)
    return EngineBar(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts.replace(minute=15),
        open_price=Decimal("10.0"),
        high_price=Decimal("10.8"),
        low_price=Decimal("9.8"),
        close_price=Decimal("10.5"),
        volume=1000,
    )


def make_structure(symbol_id: uuid.UUID, timeframe: Timeframe, hour: int) -> StructureEngineResult:
    ts = datetime(2026, 3, 11, hour, 0, tzinfo=timezone.utc)
    return StructureEngineResult(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts.replace(minute=15),
        config_version="v1",
        pivot_window=2,
        swing_points=[],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=None,
            bullish_bos_reference_timestamp=None,
            bullish_bos_protected_low_price=None,
            bullish_bos_protected_low_timestamp=None,
            bearish_bos_reference_price=None,
            bearish_bos_reference_timestamp=None,
            bearish_bos_protected_high_price=None,
            bearish_bos_protected_high_timestamp=None,
            bullish_choch_reference_price=None,
            bullish_choch_reference_timestamp=None,
            bearish_choch_reference_price=None,
            bearish_choch_reference_timestamp=None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("9.8"),
        active_range_low_timestamp=ts,
        active_range_high=Decimal("10.8"),
        active_range_high_timestamp=ts,
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=[],
    )


def make_zone(symbol_id: uuid.UUID, timeframe: Timeframe, hour: int) -> ZoneEngineResult:
    ts = datetime(2026, 3, 11, hour, 0, tzinfo=timezone.utc)
    return ZoneEngineResult(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts.replace(minute=15),
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("9.8"),
        active_swing_low_timestamp=ts,
        active_swing_high=Decimal("10.8"),
        active_swing_high_timestamp=ts,
        range_width=Decimal("1.0"),
        equilibrium=Decimal("10.3"),
        equilibrium_band_low=Decimal("10.2"),
        equilibrium_band_high=Decimal("10.4"),
        zone_location="DISCOUNT",
        distance_from_equilibrium=Decimal("0.2"),
        distance_from_equilibrium_pct_of_range=Decimal("0.2"),
    )


def make_pattern(symbol_id: uuid.UUID, timeframe: Timeframe, hour: int) -> PatternEngineResult:
    ts = datetime(2026, 3, 11, hour, 0, tzinfo=timezone.utc)
    return PatternEngineResult(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts.replace(minute=15),
        config_version="v1",
        compression=CompressionResult(status="NOT_COMPRESSED", criteria_met=[], lookback_bars=5),
        bullish_displacement=DisplacementResult(
            status="NONE",
            mode=None,
            event_timestamp=None,
            reference_price=None,
            reference_timestamp=None,
            range_multiple_atr=None,
            close_location_ratio=None,
        ),
        bullish_reclaim=LifecyclePatternResult(
            status="ACTIVE",
            reference_price=Decimal("10.0"),
            reference_timestamp=ts,
            sweep_low=None,
            candidate_start_timestamp=ts,
            event_timestamp=ts,
        ),
        bullish_fake_breakdown=LifecyclePatternResult(
            status="NONE",
            reference_price=None,
            reference_timestamp=None,
            sweep_low=None,
            candidate_start_timestamp=None,
            event_timestamp=None,
        ),
        bullish_trap_reverse=TrapReverseResult(
            status="NONE",
            reference_price=None,
            reference_timestamp=None,
            trigger_event=None,
            event_timestamp=None,
        ),
        recontainment=RecontainmentResult(
            status="CANDIDATE",
            source_displacement_timestamp=None,
            source_displacement_reference_price=None,
            candidate_start_timestamp=ts,
            active_range_low=Decimal("9.8"),
            active_range_high=Decimal("10.8"),
        ),
        events_on_bar=[],
        active_flags=[],
    )


def make_phase2_context(symbol_id: uuid.UUID) -> PersistedPhase2Context:
    htf = PersistedFramePhase2Context(
        structure=make_structure(symbol_id, Timeframe.HOUR_4, 4),
        structure_history=[make_structure(symbol_id, Timeframe.HOUR_4, 4)],
        zone=make_zone(symbol_id, Timeframe.HOUR_4, 4),
        pattern=make_pattern(symbol_id, Timeframe.HOUR_4, 4),
    )
    mtf = PersistedFramePhase2Context(
        structure=make_structure(symbol_id, Timeframe.HOUR_1, 9),
        structure_history=[make_structure(symbol_id, Timeframe.HOUR_1, 9)],
        zone=make_zone(symbol_id, Timeframe.HOUR_1, 9),
        pattern=make_pattern(symbol_id, Timeframe.HOUR_1, 9),
    )
    ltf = PersistedFramePhase2Context(
        structure=make_structure(symbol_id, Timeframe.MIN_15, 10),
        structure_history=[make_structure(symbol_id, Timeframe.MIN_15, 10)],
        zone=make_zone(symbol_id, Timeframe.MIN_15, 10),
        pattern=make_pattern(symbol_id, Timeframe.MIN_15, 10),
    )
    return PersistedPhase2Context(htf=htf, mtf=mtf, ltf=ltf, micro=None)


def make_symbol_context(symbol_id: uuid.UUID) -> SymbolMarketContext:
    return SymbolMarketContext(
        htf_bar=make_bar(symbol_id, Timeframe.HOUR_4, 4),
        mtf_bar=make_bar(symbol_id, Timeframe.HOUR_1, 9),
        ltf_bar=make_bar(symbol_id, Timeframe.MIN_15, 10),
        micro_bar=None,
    )


def make_benchmark_context() -> BenchmarkPhaseContext:
    indexes = []
    for ticker in ("SPY", "QQQ", "IWM"):
        symbol_id = uuid.uuid4()
        structure = make_structure(symbol_id, Timeframe.HOUR_4, 4)
        indexes.append(
            RegimeIndexInput(
                ticker=ticker,
                latest_bar=make_bar(symbol_id, Timeframe.HOUR_4, 4),
                structure=structure,
                zone=make_zone(symbol_id, Timeframe.HOUR_4, 4),
                pattern=make_pattern(symbol_id, Timeframe.HOUR_4, 4),
                structure_history=[structure],
            )
        )
    return BenchmarkPhaseContext(market_indexes=indexes)


def make_regime_input(symbol: UniverseSymbolContext, benchmark_context: BenchmarkPhaseContext) -> RegimeEngineInput:
    sector_symbol = uuid.uuid4()
    sector_structure = make_structure(sector_symbol, Timeframe.HOUR_1, 9)
    return RegimeEngineInput(
        market_indexes=benchmark_context.market_indexes,
        sector=SectorRegimeInput(
            sector_name="Tech",
            sector_etf_ticker="XLK",
            latest_bar=make_bar(sector_symbol, Timeframe.HOUR_1, 9),
            structure=sector_structure,
            zone=make_zone(sector_symbol, Timeframe.HOUR_1, 9),
            pattern=make_pattern(sector_symbol, Timeframe.HOUR_1, 9),
            structure_history=[sector_structure],
            relative_strength_vs_spy=Decimal("0.03"),
            momentum_persistence_score=Decimal("0.70"),
        ),
        stock_relative=StockRelativeRegimeInput(
            symbol_id=symbol.symbol_id,
            ticker=symbol.ticker,
            sector_name="Tech",
            latest_bar=make_bar(symbol.symbol_id, Timeframe.HOUR_1, 9),
            relative_strength_vs_spy=Decimal("0.02"),
            relative_strength_vs_sector=Decimal("0.01"),
            structure_quality_score=Decimal("0.80"),
        ),
        breadth=BreadthInput(
            advance_decline_ratio=Decimal("1.30"),
            up_volume_ratio=Decimal("1.10"),
            known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        ),
        volatility=VolatilityInput(
            realized_volatility_20d=Decimal("0.10"),
            realized_volatility_5d=Decimal("0.09"),
            known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        ),
    )


def make_event_risk_input(symbol: UniverseSymbolContext) -> EventRiskEngineInput:
    return EventRiskEngineInput(
        symbol_id=symbol.symbol_id,
        ticker=symbol.ticker,
        signal_timestamp=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
        earnings=None,
        corporate_events=[],
        news_risks=[],
        halt_risk=None,
    )


def make_signal_result(symbol: UniverseSymbolContext) -> SignalEngineResult:
    ts = datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc)
    known = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    return SignalEngineResult(
        symbol_id=symbol.symbol_id,
        ticker=symbol.ticker,
        universe_snapshot_id=symbol.universe_snapshot_id,
        signal_timestamp=ts,
        known_at=known,
        htf_bar_timestamp=datetime(2026, 3, 11, 4, 0, tzinfo=timezone.utc),
        mtf_bar_timestamp=datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc),
        ltf_bar_timestamp=ts,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.85"),
        grade="A",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": "LTF_BULLISH_CHOCH"},
    )


def make_trade_plan_result(signal_id: uuid.UUID, symbol: UniverseSymbolContext) -> TradePlanEngineResult:
    ts = datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc)
    known = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    return TradePlanEngineResult(
        signal_id=signal_id,
        symbol_id=symbol.symbol_id,
        ticker=symbol.ticker,
        plan_timestamp=ts,
        known_at=known,
        entry_type="BASE",
        entry_zone_low=Decimal("10.00"),
        entry_zone_high=Decimal("10.50"),
        confirmation_level=Decimal("10.60"),
        invalidation_level=Decimal("10.00"),
        tp1=Decimal("11.40"),
        tp2=Decimal("12.00"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def make_regime_result() -> RegimeEngineResult:
    return RegimeEngineResult(
        config_version="v1",
        market_regime="BULLISH_TREND",
        sector_regime="SECTOR_STRONG",
        market_permission_score=Decimal("0.30"),
        sector_permission_score=Decimal("0.20"),
        stock_structure_quality_score=Decimal("0.80"),
        allows_longs=True,
        coverage_complete=True,
        reason_codes=["MARKET_BULLISH_TREND", "SECTOR_STRONG"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={"stock_relative_snapshot": {"relative_strength_vs_sector": "0.01"}},
    )


def make_event_risk_result() -> EventRiskEngineResult:
    return EventRiskEngineResult(
        config_version="v1",
        event_risk_class="NO_EVENT_RISK",
        blocked=False,
        coverage_complete=True,
        soft_penalty=Decimal("0.0000"),
        reason_codes=["EVENT_RISK_CLEAR"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def make_ranking_result(signal_id: uuid.UUID, symbol: UniverseSymbolContext):
    from doctrine_engine.ranking.models import RankingEngineResult

    return RankingEngineResult(
        config_version="v1",
        signal_id=signal_id,
        symbol_id=symbol.symbol_id,
        ticker=symbol.ticker,
        ranking_state="RANKED",
        ranking_tier="HIGH",
        ranking_grade="R2",
        ranking_label="BASELINE_HIGH",
        baseline_score=Decimal("0.7000"),
        final_score=Decimal("0.7800"),
        reason_codes=["RANK_BULLISH_TREND", "RANK_TIER_HIGH"],
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
        extensible_context={},
    )


def make_alert_decision(signal_id: uuid.UUID, symbol: UniverseSymbolContext) -> AlertDecisionResult:
    payload = AlertDecisionPayload(
        symbol_id=symbol.symbol_id,
        ticker=symbol.ticker,
        signal="LONG",
        confidence=Decimal("0.85"),
        grade="A",
        setup_state="RECONTAINMENT_CONFIRMED",
        market_regime="BULLISH_TREND",
        sector_regime="SECTOR_STRONG",
        event_risk_class="NO_EVENT_RISK",
        entry_type="BASE",
        entry_zone_low=Decimal("10.00"),
        entry_zone_high=Decimal("10.50"),
        confirmation_level=Decimal("10.60"),
        invalidation_level=Decimal("10.00"),
        tp1=Decimal("11.40"),
        tp2=Decimal("12.00"),
        signal_timestamp=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
        alert_state="NEW",
        priority="STANDARD",
        operator_summary="summary",
        reason_codes=["PRICE_RANGE_VALID"],
        micro_state="NOT_REQUESTED",
        micro_present=False,
        micro_trigger_state=None,
        micro_used_for_confirmation=False,
        snapshot_path=None,
    )
    return AlertDecisionResult(
        send=True,
        alert_state="NEW",
        suppression_reason=None,
        priority="STANDARD",
        dedup_key=str(signal_id),
        family_key=f"{symbol.symbol_id}:RECONTAINMENT_CONFIRMED:BASE",
        payload_fingerprint="fingerprint",
        payload=payload,
        snapshot_request=None,
    )


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []


class UniverseLoader:
    def __init__(self, recorder: Recorder, symbol: UniverseSymbolContext) -> None:
        self.recorder = recorder
        self.symbol = symbol

    def load(self, runner_input):
        self.recorder.calls.append("LOAD_UNIVERSE_CONTEXT")
        return [self.symbol]


class MarketLoader:
    def __init__(self, recorder: Recorder, symbol_context: SymbolMarketContext, benchmark_context: BenchmarkPhaseContext) -> None:
        self.recorder = recorder
        self.symbol_context = symbol_context
        self.benchmark_context = benchmark_context

    def load_symbol_context(self, symbol, runner_input):
        self.recorder.calls.append("LOAD_SYMBOL_MARKET_CONTEXT")
        return self.symbol_context

    def load_benchmark_context(self, runner_input):
        self.recorder.calls.append("LOAD_BENCHMARK_CONTEXT")
        return self.benchmark_context


class Phase2Loader:
    def __init__(self, recorder: Recorder, phase2_context: PersistedPhase2Context) -> None:
        self.recorder = recorder
        self.phase2_context = phase2_context

    def load(self, symbol, runner_input):
        self.recorder.calls.append("LOAD_PHASE2_CONTEXT")
        return self.phase2_context


class RegimeInputLoader:
    def __init__(self, recorder: Recorder, regime_input: RegimeEngineInput) -> None:
        self.recorder = recorder
        self.regime_input = regime_input

    def load(self, symbol, benchmark_context, runner_input):
        self.recorder.calls.append("LOAD_REGIME_EXTERNAL_INPUT")
        return self.regime_input


class EventRiskInputLoader:
    def __init__(self, recorder: Recorder, event_risk_input: EventRiskEngineInput) -> None:
        self.recorder = recorder
        self.event_risk_input = event_risk_input

    def load(self, symbol, signal_time_baseline, known_at_baseline, runner_input):
        self.recorder.calls.append("LOAD_EVENT_RISK_EXTERNAL_INPUT")
        return self.event_risk_input


class PriorAlertLoader:
    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder

    def load(self, symbol_id, setup_state, entry_type):
        self.recorder.calls.append("LOAD_PRIOR_ALERT_STATE")
        return None


class FakeSignalEngine:
    def __init__(self, recorder: Recorder, result: SignalEngineResult) -> None:
        self.recorder = recorder
        self.result = result

    def evaluate(self, signal_input):
        self.recorder.calls.append("BUILD_SIGNAL")
        return self.result


class FakeTradePlanEngine:
    def __init__(self, recorder: Recorder, result: TradePlanEngineResult) -> None:
        self.recorder = recorder
        self.result = result

    def build_plan(self, trade_plan_input):
        self.recorder.calls.append("BUILD_TRADE_PLAN")
        return self.result


class FakeRegimeEngine:
    def __init__(self, recorder: Recorder, result: RegimeEngineResult) -> None:
        self.recorder = recorder
        self.result = result

    def evaluate(self, regime_input):
        self.recorder.calls.append("BUILD_REGIME")
        return self.result


class FakeEventRiskEngine:
    def __init__(self, recorder: Recorder, result: EventRiskEngineResult) -> None:
        self.recorder = recorder
        self.result = result

    def evaluate(self, event_risk_input):
        self.recorder.calls.append("BUILD_EVENT_RISK")
        return self.result


class FakeRankingEngine:
    def __init__(self, recorder: Recorder, result) -> None:
        self.recorder = recorder
        self.result = result

    def evaluate(self, ranking_input):
        self.recorder.calls.append("BUILD_RANKING")
        return self.result


class FakeAlertWorkflow:
    def __init__(self, recorder: Recorder, result: AlertDecisionResult) -> None:
        self.recorder = recorder
        self.result = result

    def evaluate(self, workflow_input):
        self.recorder.calls.append("BUILD_ALERT_DECISION")
        return self.result


class FakeRenderer:
    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder

    def render(self, payload):
        from doctrine_engine.alerts.models import TelegramRenderResult

        self.recorder.calls.append("RENDER_ALERT_TEXT")
        return TelegramRenderResult(text="rendered")


def test_runner_executes_stages_in_exact_order() -> None:
    recorder = Recorder()
    symbol = UniverseSymbolContext(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=["UNIVERSE_ELIGIBLE"],
        universe_known_at=datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc),
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
        ranking_engine=FakeRankingEngine(recorder, make_ranking_result(uuid.uuid4(), symbol)),
        alert_workflow_factory=lambda config: FakeAlertWorkflow(recorder, make_alert_decision(uuid.uuid4(), symbol)),
        telegram_renderer=FakeRenderer(recorder),
    )

    pipeline.run(
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

    assert recorder.calls == [
        "LOAD_UNIVERSE_CONTEXT",
        "LOAD_BENCHMARK_CONTEXT",
        "LOAD_PHASE2_CONTEXT",
        "LOAD_SYMBOL_MARKET_CONTEXT",
        "LOAD_REGIME_EXTERNAL_INPUT",
        "BUILD_REGIME",
        "LOAD_EVENT_RISK_EXTERNAL_INPUT",
        "BUILD_EVENT_RISK",
        "BUILD_SIGNAL",
        "BUILD_TRADE_PLAN",
        "BUILD_RANKING",
        "LOAD_PRIOR_ALERT_STATE",
        "BUILD_ALERT_DECISION",
        "RENDER_ALERT_TEXT",
    ]
