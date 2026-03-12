from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    SignalEngineInput,
    SignalEventRiskInput,
    SignalFrameInput,
    SignalRegimeInput,
    SignalSectorContextInput,
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.signal_engine import SignalEngine, SignalEngineConfig


def _bar(symbol_id: uuid.UUID, timeframe: Timeframe, ts: datetime, close: str, known_offset_minutes: int = 15) -> EngineBar:
    close_price = Decimal(close)
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=known_offset_minutes), close_price, close_price + Decimal("0.2"), close_price - Decimal("0.2"), close_price)


def _structure_result(bar: EngineBar, events: list[StructureEvent] | None = None) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=2), bar.bar_timestamp - timedelta(hours=1), Decimal("9.0"), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=1), bar.bar_timestamp - timedelta(minutes=30), Decimal("11.0"), 1),
            SwingPoint("LOW", bar.bar_timestamp - timedelta(minutes=20), bar.bar_timestamp - timedelta(minutes=10), Decimal("9.8"), 2),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(minutes=5), bar.bar_timestamp, Decimal("10.8"), 3),
        ],
        reference_levels=StructureReferenceLevels(Decimal("11.0"), bar.bar_timestamp - timedelta(hours=1), Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), Decimal("10.8"), bar.bar_timestamp - timedelta(minutes=5), None, None, None, None),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("9.8"),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
        active_range_high=Decimal("11.0"),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=events or [],
    )


def _zone_result(bar: EngineBar) -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("9.8"),
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
        active_swing_high=Decimal("11.0"),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        range_width=Decimal("1.2"),
        equilibrium=Decimal("10.4"),
        equilibrium_band_low=Decimal("10.34"),
        equilibrium_band_high=Decimal("10.46"),
        zone_location="DISCOUNT",
        distance_from_equilibrium=Decimal("-0.2"),
        distance_from_equilibrium_pct_of_range=Decimal("-0.1667"),
    )


def _pattern_result(bar: EngineBar, recontainment: str = "ACTIVE") -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult("NOT_COMPRESSED", [], 5),
        bullish_displacement=DisplacementResult("NONE", None, None, None, None, None, None),
        bullish_reclaim=LifecyclePatternResult("NONE", None, None, None, None, None),
        bullish_fake_breakdown=LifecyclePatternResult("NONE", None, None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("NONE", None, None, None, None),
        recontainment=RecontainmentResult(recontainment, None, None, None, Decimal("9.8"), Decimal("11.0")),
        events_on_bar=[],
        active_flags=["RECONTAINMENT_ACTIVE"] if recontainment == "ACTIVE" else [],
    )


def _frame_input(name: str, bar: EngineBar, structure: StructureEngineResult, zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure, [structure], zone, pattern)


def _signal_input(*, htf_history, htf_zone, mtf_history, mtf_zone, mtf_pattern, ltf_history, ltf_zone, ltf_pattern) -> SignalEngineInput:
    symbol_id = htf_history[-1].symbol_id
    htf_bar = EngineBar(symbol_id, Timeframe.HOUR_4, htf_history[-1].bar_timestamp, htf_history[-1].known_at, Decimal("10.5"), Decimal("10.7"), Decimal("10.3"), Decimal("10.5"))
    mtf_bar = EngineBar(symbol_id, Timeframe.HOUR_1, mtf_history[-1].bar_timestamp, mtf_history[-1].known_at, Decimal("10.3"), Decimal("10.5"), Decimal("10.1"), Decimal("10.3"))
    ltf_bar = EngineBar(symbol_id, Timeframe.MIN_15, ltf_history[-1].bar_timestamp, ltf_history[-1].known_at, Decimal("10.4"), Decimal("10.6"), Decimal("10.2"), Decimal("10.4"))
    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=[],
        universe_known_at=htf_history[-1].known_at,
        htf=_frame_input("4H", htf_bar, htf_history[-1], htf_zone, _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_history[-1], mtf_zone, mtf_pattern),
        ltf=_frame_input("15M", ltf_bar, ltf_history[-1], ltf_zone, ltf_pattern),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_history[-1].known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_history[-1].known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_history[-1].known_at),
    )


def test_signal_timestamp_uses_ltf_by_default_and_known_at_uses_consumed_inputs_only() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts - timedelta(hours=4), "10.5", known_offset_minutes=15)
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts - timedelta(hours=1), "10.3", known_offset_minutes=20)
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4", known_offset_minutes=25)
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        universe_known_at=ts + timedelta(minutes=5),
        regime=replace(signal_input.regime, known_at=ts + timedelta(minutes=10)),
        event_risk=replace(signal_input.event_risk, known_at=ts + timedelta(minutes=12)),
        sector_context=replace(signal_input.sector_context, known_at=ts + timedelta(minutes=8)),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.signal_timestamp == ltf_bar.bar_timestamp
    assert result.known_at == ltf_bar.known_at
    assert result.extensible_context["micro_state"] == "NOT_REQUESTED"


def test_micro_present_but_config_off_does_not_affect_signal_timestamp_or_known_at() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts - timedelta(hours=4), "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts - timedelta(hours=1), "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4", known_offset_minutes=25)
    micro_bar = _bar(symbol_id, Timeframe.MIN_5, ts + timedelta(minutes=5), "10.5", known_offset_minutes=40)
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        micro=SignalFrameInput(
            timeframe="5M",
            latest_bar=micro_bar,
            structure=_structure_result(micro_bar, events=[StructureEvent("BULLISH_CHOCH", micro_bar.bar_timestamp, micro_bar.bar_timestamp, Decimal("10.4"), Decimal("10.5"))]),
            structure_history=[_structure_result(micro_bar, events=[StructureEvent("BULLISH_CHOCH", micro_bar.bar_timestamp, micro_bar.bar_timestamp, Decimal("10.4"), Decimal("10.5"))])],
            zone=_zone_result(micro_bar),
            pattern=_pattern_result(micro_bar),
        ),
    )

    result = SignalEngine(SignalEngineConfig(micro_context_requested=True)).evaluate(signal_input)

    assert result.signal_timestamp == ltf_bar.bar_timestamp
    assert result.known_at == ltf_bar.known_at
    assert result.extensible_context["micro_state"] == "AVAILABLE_NOT_USED"
    assert result.extensible_context["micro_present"] is True
    assert result.extensible_context["micro_used_for_confirmation"] is False
    assert result.extensible_context["micro_trigger_state"] == "LTF_BULLISH_CHOCH"


def test_micro_required_and_present_uses_micro_timestamps() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts - timedelta(hours=4), "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts - timedelta(hours=1), "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4", known_offset_minutes=25)
    micro_bar = _bar(symbol_id, Timeframe.MIN_5, ts + timedelta(minutes=5), "10.5", known_offset_minutes=40)
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )
    micro_structure = _structure_result(micro_bar, events=[StructureEvent("BULLISH_CHOCH", micro_bar.bar_timestamp, micro_bar.bar_timestamp, Decimal("10.4"), Decimal("10.5"))])
    signal_input = replace(
        signal_input,
        micro=SignalFrameInput(
            timeframe="5M",
            latest_bar=micro_bar,
            structure=micro_structure,
            structure_history=[micro_structure],
            zone=_zone_result(micro_bar),
            pattern=_pattern_result(micro_bar),
        ),
    )

    result = SignalEngine(SignalEngineConfig(require_micro_confirmation=True)).evaluate(signal_input)

    assert result.signal_timestamp == micro_bar.bar_timestamp
    assert result.known_at == micro_bar.known_at
    assert result.extensible_context["micro_state"] == "AVAILABLE_USED"


def test_micro_requested_and_missing_is_reported_as_requested_unavailable() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 4, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts - timedelta(hours=4), "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts - timedelta(hours=1), "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4", known_offset_minutes=25)
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    result = SignalEngine(SignalEngineConfig(require_micro_confirmation=True)).evaluate(signal_input)

    assert result.extensible_context["micro_state"] == "REQUESTED_UNAVAILABLE"
