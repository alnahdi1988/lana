from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    SignalEngineInput,
    SignalEngineResult,
    SignalEventRiskInput,
    SignalFrameInput,
    SignalRegimeInput,
    SignalSectorContextInput,
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    TradePlanEngineInput,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.trade_plan_engine import TradePlanEngine


def _bar(symbol_id: uuid.UUID, timeframe: Timeframe, ts: datetime, close: str) -> EngineBar:
    close_price = Decimal(close)
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=15), close_price, close_price + Decimal("0.25"), close_price - Decimal("0.25"), close_price)


def _structure_result(bar: EngineBar, *, swing_highs: list[str], swing_lows: list[str]) -> StructureEngineResult:
    swings = [
        SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=4), bar.bar_timestamp - timedelta(hours=3), Decimal(swing_lows[0]), 0),
        SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=3), bar.bar_timestamp - timedelta(hours=2), Decimal(swing_highs[0]), 1),
        SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=2), bar.bar_timestamp - timedelta(hours=1), Decimal(swing_lows[1]), 2),
        SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=1), bar.bar_timestamp, Decimal(swing_highs[1]), 3),
    ]
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=swings,
        reference_levels=StructureReferenceLevels(
            Decimal(swing_highs[1]),
            bar.bar_timestamp - timedelta(hours=1),
            Decimal(swing_lows[1]),
            bar.bar_timestamp - timedelta(hours=2),
            Decimal(swing_lows[1]),
            bar.bar_timestamp - timedelta(hours=2),
            Decimal(swing_highs[1]),
            bar.bar_timestamp - timedelta(hours=1),
            None,
            None,
            None,
            None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal(swing_lows[1]),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(hours=2),
        active_range_high=Decimal(swing_highs[1]),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=[],
    )


def _zone_result(bar: EngineBar, *, low: str, high: str, eq: str, eq_low: str, eq_high: str, zone_location: str = "DISCOUNT") -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal(low),
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(hours=2),
        active_swing_high=Decimal(high),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        range_width=Decimal(high) - Decimal(low),
        equilibrium=Decimal(eq),
        equilibrium_band_low=Decimal(eq_low),
        equilibrium_band_high=Decimal(eq_high),
        zone_location=zone_location,
        distance_from_equilibrium=Decimal("0.00"),
        distance_from_equilibrium_pct_of_range=Decimal("0.00"),
    )


def _pattern_result(bar: EngineBar, *, reclaim_ref: str = "9.75", active_range_low: str = "9.80") -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult("NOT_COMPRESSED", [], 5),
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.30"), bar.bar_timestamp, Decimal("1.7"), Decimal("0.82")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal(reclaim_ref), bar.bar_timestamp - timedelta(minutes=20), Decimal("9.92"), bar.bar_timestamp - timedelta(minutes=10), bar.bar_timestamp - timedelta(minutes=5)),
        bullish_fake_breakdown=LifecyclePatternResult("ACTIVE", Decimal("9.95"), bar.bar_timestamp - timedelta(minutes=30), Decimal("9.90"), bar.bar_timestamp - timedelta(minutes=15), bar.bar_timestamp - timedelta(minutes=5)),
        bullish_trap_reverse=TrapReverseResult("ACTIVE", Decimal("9.96"), bar.bar_timestamp - timedelta(minutes=40), "BULLISH_CHOCH", bar.bar_timestamp - timedelta(minutes=5)),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=15), Decimal("10.20"), bar.bar_timestamp - timedelta(minutes=10), Decimal(active_range_low), Decimal("11.20")),
        events_on_bar=[],
        active_flags=["BULLISH_RECLAIM", "RECONTAINMENT_ACTIVE"],
    )


def _frame_input(name: str, bar: EngineBar, structure: StructureEngineResult, zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure, [structure], zone, pattern)


def _signal_source(symbol_id: uuid.UUID) -> SignalEngineInput:
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc), "11.10")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc), "10.70")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc), "10.85")

    htf_structure = _structure_result(htf_bar, swing_highs=["12.20", "12.80"], swing_lows=["9.20", "9.60"])
    mtf_structure = _structure_result(mtf_bar, swing_highs=["11.20", "11.60"], swing_lows=["9.70", "9.85"])
    ltf_structure = _structure_result(ltf_bar, swing_highs=["10.95", "11.05"], swing_lows=["9.90", "10.00"])
    ltf_structure = replace(
        ltf_structure,
        events_on_bar=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp - timedelta(minutes=15), Decimal("10.90"), Decimal("10.90"))],
    )

    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.85"),
        universe_reason_codes=[],
        universe_known_at=htf_bar.known_at,
        htf=_frame_input("4H", htf_bar, htf_structure, _zone_result(htf_bar, low="9.60", high="12.80", eq="11.20", eq_low="10.95", eq_high="11.45"), _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_structure, _zone_result(mtf_bar, low="9.85", high="11.60", eq="10.70", eq_low="10.45", eq_high="10.95"), _pattern_result(mtf_bar)),
        ltf=_frame_input("15M", ltf_bar, ltf_structure, _zone_result(ltf_bar, low="10.00", high="11.05", eq="10.55", eq_low="10.35", eq_high="10.75"), _pattern_result(ltf_bar)),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_bar.known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_bar.known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_bar.known_at),
    )


def _signal_result(signal_source: SignalEngineInput, *, setup_state: str, ltf_trigger_state: str = "LTF_BULLISH_RECLAIM") -> SignalEngineResult:
    return SignalEngineResult(
        symbol_id=signal_source.symbol_id,
        ticker=signal_source.ticker,
        universe_snapshot_id=None,
        signal_timestamp=signal_source.ltf.latest_bar.bar_timestamp,
        known_at=signal_source.ltf.latest_bar.known_at,
        htf_bar_timestamp=signal_source.htf.latest_bar.bar_timestamp,
        mtf_bar_timestamp=signal_source.mtf.latest_bar.bar_timestamp,
        ltf_bar_timestamp=signal_source.ltf.latest_bar.bar_timestamp,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade="A",
        bias_htf="BULLISH",
        setup_state=setup_state,
        reason_codes=[],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": ltf_trigger_state},
    )


def test_invalidation_anchor_priority_for_reclaim_and_recontainment() -> None:
    engine = TradePlanEngine()
    reclaim_source = _signal_source(uuid.uuid4())
    reclaim_result = _signal_result(reclaim_source, setup_state="BULLISH_RECLAIM")
    reclaim_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), reclaim_result, reclaim_source))
    assert reclaim_plan.invalidation_level == Decimal("9.75")
    assert reclaim_plan.plan_reason_codes[1] == "INVALIDATION_BELOW_RECLAIM_FAILURE"

    recontain_source = _signal_source(uuid.uuid4())
    recontain_result = _signal_result(recontain_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_BULLISH_CHOCH")
    recontain_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), recontain_result, recontain_source))
    assert recontain_plan.invalidation_level == Decimal("9.80")
    assert recontain_plan.plan_reason_codes[1] == "INVALIDATION_BELOW_RECONTAINMENT_RANGE"


def test_invalidation_anchor_inside_entry_zone_raises() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_source = replace(
        signal_source,
        mtf=replace(signal_source.mtf, pattern=_pattern_result(signal_source.mtf.latest_bar, active_range_low="10.10")),
    )
    signal_result = _signal_result(signal_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_NO_TRIGGER")

    with pytest.raises(ValueError, match="inside the entry zone"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))


def test_tp1_rules_and_tp2_duplicate_exclusion() -> None:
    engine = TradePlanEngine()

    reclaim_source = _signal_source(uuid.uuid4())
    updated_ltf_structure = replace(
        reclaim_source.ltf.structure,
        swing_points=[
            SwingPoint("LOW", reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=4), reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=3), Decimal("9.90"), 0),
            SwingPoint("HIGH", reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=3), reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=2), Decimal("11.10"), 1),
            SwingPoint("LOW", reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=2), reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=1), Decimal("10.00"), 2),
            SwingPoint("HIGH", reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(hours=1), reclaim_source.ltf.latest_bar.bar_timestamp, Decimal("11.20"), 3),
        ],
        events_on_bar=[StructureEvent("BULLISH_CHOCH", reclaim_source.ltf.latest_bar.bar_timestamp, reclaim_source.ltf.latest_bar.bar_timestamp - timedelta(minutes=15), Decimal("10.80"), Decimal("10.90"))],
    )
    reclaim_source = replace(
        reclaim_source,
        mtf=replace(reclaim_source.mtf, zone=replace(reclaim_source.mtf.zone, equilibrium=Decimal("11.00"))),
        ltf=replace(
            reclaim_source.ltf,
            structure=updated_ltf_structure,
            structure_history=[updated_ltf_structure],
            zone=replace(reclaim_source.ltf.zone, active_swing_high=Decimal("11.20")),
        ),
    )
    reclaim_result = _signal_result(reclaim_source, setup_state="BULLISH_RECLAIM")
    reclaim_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), reclaim_result, reclaim_source))
    assert reclaim_plan.tp1 == Decimal("11.00")
    assert reclaim_plan.plan_reason_codes[2] == "TP1_AT_EQUILIBRIUM_RETURN"
    assert reclaim_plan.tp2 == Decimal("11.60")

    equilibrium_source = _signal_source(uuid.uuid4())
    equilibrium_ltf_structure = replace(
        equilibrium_source.ltf.structure,
        swing_points=[
            SwingPoint("LOW", equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=4), equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=3), Decimal("9.90"), 0),
            SwingPoint("HIGH", equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=3), equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=2), Decimal("11.20"), 1),
            SwingPoint("LOW", equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=2), equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=1), Decimal("10.00"), 2),
            SwingPoint("HIGH", equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(hours=1), equilibrium_source.ltf.latest_bar.bar_timestamp, Decimal("11.25"), 3),
        ],
        events_on_bar=[StructureEvent("BULLISH_CHOCH", equilibrium_source.ltf.latest_bar.bar_timestamp, equilibrium_source.ltf.latest_bar.bar_timestamp - timedelta(minutes=15), Decimal("11.00"), Decimal("11.10"))],
    )
    equilibrium_source = replace(
        equilibrium_source,
        mtf=replace(equilibrium_source.mtf, zone=replace(equilibrium_source.mtf.zone, zone_location="EQUILIBRIUM")),
        ltf=replace(
            equilibrium_source.ltf,
            structure=equilibrium_ltf_structure,
            structure_history=[equilibrium_ltf_structure],
            zone=replace(equilibrium_source.ltf.zone, active_swing_high=Decimal("11.25")),
        ),
    )
    equilibrium_result = _signal_result(equilibrium_source, setup_state="EQUILIBRIUM_HOLD", ltf_trigger_state="LTF_NO_TRIGGER")
    equilibrium_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), equilibrium_result, equilibrium_source))
    assert equilibrium_plan.plan_reason_codes[2] == "TP1_AT_INTERNAL_LIQUIDITY"
    assert equilibrium_plan.tp1 != equilibrium_source.mtf.zone.equilibrium


def test_missing_tp2_candidate_raises() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_source = replace(
        signal_source,
        htf=replace(
            signal_source.htf,
            zone=replace(signal_source.htf.zone, active_swing_high=Decimal("10.70")),
            structure=_structure_result(signal_source.htf.latest_bar, swing_highs=["10.50", "10.70"], swing_lows=["9.20", "9.60"]),
            structure_history=[_structure_result(signal_source.htf.latest_bar, swing_highs=["10.50", "10.70"], swing_lows=["9.20", "9.60"])],
        ),
        mtf=replace(signal_source.mtf, zone=replace(signal_source.mtf.zone, active_swing_high=Decimal("10.70"))),
    )
    signal_result = _signal_result(signal_source, setup_state="BULLISH_RECLAIM")

    with pytest.raises(ValueError, match="TP2"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))
