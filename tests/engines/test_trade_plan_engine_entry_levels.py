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
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=15), close_price, close_price + Decimal("0.40"), close_price - Decimal("0.40"), close_price)


def _structure_event(event_type: str, ts: datetime, reference_price: str) -> StructureEvent:
    return StructureEvent(event_type, ts, ts - timedelta(minutes=15), Decimal(reference_price), Decimal(reference_price) + Decimal("0.10"))


def _structure_result(bar: EngineBar, *, high: str, low: str, events_on_bar: list[StructureEvent] | None = None) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=3), bar.bar_timestamp - timedelta(hours=2), Decimal(low), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=2), bar.bar_timestamp - timedelta(hours=1), Decimal(high), 1),
            SwingPoint("LOW", bar.bar_timestamp - timedelta(minutes=30), bar.bar_timestamp - timedelta(minutes=15), Decimal(low) + Decimal("0.10"), 2),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(minutes=10), bar.bar_timestamp, Decimal(high) - Decimal("0.10"), 3),
        ],
        reference_levels=StructureReferenceLevels(
            Decimal(high),
            bar.bar_timestamp - timedelta(hours=2),
            Decimal(low),
            bar.bar_timestamp - timedelta(hours=3),
            Decimal(low),
            bar.bar_timestamp - timedelta(hours=3),
            Decimal(high),
            bar.bar_timestamp - timedelta(hours=2),
            Decimal(high) - Decimal("0.20"),
            bar.bar_timestamp - timedelta(minutes=10),
            None,
            None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal(low),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(hours=3),
        active_range_high=Decimal(high),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=2),
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=events_on_bar or [],
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
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(hours=3),
        active_swing_high=Decimal(high),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(hours=2),
        range_width=Decimal(high) - Decimal(low),
        equilibrium=Decimal(eq),
        equilibrium_band_low=Decimal(eq_low),
        equilibrium_band_high=Decimal(eq_high),
        zone_location=zone_location,
        distance_from_equilibrium=Decimal("0.00"),
        distance_from_equilibrium_pct_of_range=Decimal("0.00"),
    )


def _pattern_result(bar: EngineBar, *, reclaim_ref: str | None = "9.90", fake_ref: str | None = "10.00", trap_ref: str | None = "10.05") -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult("NOT_COMPRESSED", [], 5),
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.40"), bar.bar_timestamp, Decimal("1.8"), Decimal("0.8")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal(reclaim_ref) if reclaim_ref is not None else None, bar.bar_timestamp - timedelta(minutes=30) if reclaim_ref is not None else None, None, None, bar.bar_timestamp - timedelta(minutes=5) if reclaim_ref is not None else None),
        bullish_fake_breakdown=LifecyclePatternResult("ACTIVE", Decimal(fake_ref) if fake_ref is not None else None, bar.bar_timestamp - timedelta(minutes=40) if fake_ref is not None else None, None, None, bar.bar_timestamp - timedelta(minutes=10) if fake_ref is not None else None),
        bullish_trap_reverse=TrapReverseResult("ACTIVE" if trap_ref is not None else "NONE", Decimal(trap_ref) if trap_ref is not None else None, bar.bar_timestamp - timedelta(minutes=50) if trap_ref is not None else None, "BULLISH_CHOCH" if trap_ref is not None else None, bar.bar_timestamp - timedelta(minutes=5) if trap_ref is not None else None),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=20), Decimal("10.20"), bar.bar_timestamp - timedelta(minutes=10), Decimal("9.80"), Decimal("11.20")),
        events_on_bar=[],
        active_flags=["BULLISH_DISPLACEMENT", "BULLISH_RECLAIM", "BULLISH_FAKE_BREAKDOWN", "BULLISH_TRAP_REVERSE", "RECONTAINMENT_ACTIVE"],
    )


def _frame_input(name: str, bar: EngineBar, structure: StructureEngineResult, zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure, [structure], zone, pattern)


def _signal_source(symbol_id: uuid.UUID, *, ltf_events: list[StructureEvent] | None = None, reclaim_ref: str | None = "9.90") -> SignalEngineInput:
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc), "11.40")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc), "10.90")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc), "11.50")

    htf_structure = _structure_result(htf_bar, high="12.50", low="9.60")
    mtf_structure = _structure_result(mtf_bar, high="11.40", low="9.80")
    if ltf_events is None:
        ltf_events = [_structure_event("BULLISH_CHOCH", ltf_bar.bar_timestamp, "10.90")]
    ltf_structure = _structure_result(ltf_bar, high="11.15", low="9.95", events_on_bar=ltf_events)

    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("11.50"),
        universe_reason_codes=[],
        universe_known_at=htf_bar.known_at,
        htf=_frame_input("4H", htf_bar, htf_structure, _zone_result(htf_bar, low="9.60", high="12.50", eq="11.05", eq_low="10.80", eq_high="11.30"), _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_structure, _zone_result(mtf_bar, low="9.80", high="11.40", eq="10.60", eq_low="10.35", eq_high="10.85"), _pattern_result(mtf_bar, reclaim_ref=reclaim_ref)),
        ltf=_frame_input("15M", ltf_bar, ltf_structure, _zone_result(ltf_bar, low="9.95", high="11.15", eq="10.55", eq_low="10.35", eq_high="10.75"), _pattern_result(ltf_bar, reclaim_ref=reclaim_ref)),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_bar.known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_bar.known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_bar.known_at),
    )


def _signal_result(signal_source: SignalEngineInput, *, setup_state: str, ltf_trigger_state: str) -> SignalEngineResult:
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


def test_aggressive_base_and_confirmation_entry_types_are_selected_correctly() -> None:
    engine = TradePlanEngine()

    aggressive_source = _signal_source(uuid.uuid4())
    aggressive_result = _signal_result(aggressive_source, setup_state="BULLISH_RECLAIM", ltf_trigger_state="TRAP_REVERSE_BULLISH")
    aggressive_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), aggressive_result, aggressive_source))
    assert aggressive_plan.entry_type == "AGGRESSIVE"

    base_source = _signal_source(uuid.uuid4())
    base_result = _signal_result(base_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_NO_TRIGGER")
    base_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), base_result, base_source))
    assert base_plan.entry_type == "BASE"

    confirmation_source = _signal_source(
        uuid.uuid4(),
        ltf_events=[_structure_event("BULLISH_CHOCH", datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc), "10.90")],
    )
    confirmation_result = _signal_result(confirmation_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_BULLISH_CHOCH")
    confirmation_plan = engine.build_plan(TradePlanEngineInput(uuid.uuid4(), confirmation_result, confirmation_source))
    assert confirmation_plan.entry_type == "CONFIRMATION"
    assert confirmation_plan.plan_reason_codes[0] == "ENTRY_FROM_CONFIRMATION_BREAK"
    assert confirmation_plan.extensible_context["entry_origin"] == "RECONTAINMENT"


def test_entry_zone_comes_only_from_structure_even_when_price_is_above_zone() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_result = _signal_result(signal_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_NO_TRIGGER")

    result = TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))

    assert signal_source.ltf.latest_bar.close_price > result.entry_zone_high
    assert result.entry_zone_low == Decimal("9.90")
    assert result.entry_zone_high == Decimal("10.60")


def test_bullish_reclaim_requires_non_null_support_ref() -> None:
    signal_source = _signal_source(uuid.uuid4(), reclaim_ref=None)
    signal_source = replace(
        signal_source,
        ltf=replace(
            signal_source.ltf,
            pattern=_pattern_result(signal_source.ltf.latest_bar, reclaim_ref=None, fake_ref=None, trap_ref=None),
            zone=replace(signal_source.ltf.zone, active_swing_low=None),
        ),
        mtf=replace(signal_source.mtf, zone=replace(signal_source.mtf.zone, active_swing_low=None)),
    )
    signal_result = _signal_result(signal_source, setup_state="BULLISH_RECLAIM", ltf_trigger_state="LTF_BULLISH_RECLAIM")

    with pytest.raises(ValueError, match="support reference"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))


def test_confirmation_plan_preserves_original_entry_origin_context() -> None:
    event_time = datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc)
    signal_source = _signal_source(uuid.uuid4(), ltf_events=[_structure_event("BULLISH_BOS", event_time, "11.10")])
    signal_result = _signal_result(signal_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_BULLISH_BOS")

    result = TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))

    assert result.confirmation_level == Decimal("11.10")
    assert result.plan_reason_codes[0] == "ENTRY_FROM_CONFIRMATION_BREAK"
    assert result.extensible_context["source_ltf_trigger_state"] == "LTF_BULLISH_BOS"
    assert result.extensible_context["entry_origin"] == "RECONTAINMENT"
