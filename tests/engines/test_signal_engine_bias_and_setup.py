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
    return EngineBar(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts + timedelta(minutes=known_offset_minutes),
        open_price=close_price,
        high_price=close_price + Decimal("0.2"),
        low_price=close_price - Decimal("0.2"),
        close_price=close_price,
    )


def _structure_result(
    bar: EngineBar,
    trend_state: str = "BULLISH_SEQUENCE",
    events: list[StructureEvent] | None = None,
) -> StructureEngineResult:
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
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=Decimal("11.0"),
            bullish_bos_reference_timestamp=bar.bar_timestamp - timedelta(hours=1),
            bullish_bos_protected_low_price=Decimal("9.8"),
            bullish_bos_protected_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
            bearish_bos_reference_price=Decimal("9.8"),
            bearish_bos_reference_timestamp=bar.bar_timestamp - timedelta(minutes=20),
            bearish_bos_protected_high_price=Decimal("10.8"),
            bearish_bos_protected_high_timestamp=bar.bar_timestamp - timedelta(minutes=5),
            bullish_choch_reference_price=None,
            bullish_choch_reference_timestamp=None,
            bearish_choch_reference_price=None,
            bearish_choch_reference_timestamp=None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("9.8"),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(minutes=20),
        active_range_high=Decimal("11.0"),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        trend_state=trend_state,
        events_on_bar=events or [],
    )


def _zone_result(bar: EngineBar, range_status: str = "RANGE_AVAILABLE", zone_location: str = "DISCOUNT") -> ZoneEngineResult:
    active_low = Decimal("9.8") if range_status == "RANGE_AVAILABLE" else None
    active_high = Decimal("11.0") if range_status == "RANGE_AVAILABLE" else None
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status=range_status,
        selection_reason="BRACKETING_PAIR" if range_status == "RANGE_AVAILABLE" else "NO_VALID_RANGE",
        active_swing_low=active_low,
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(minutes=20) if active_low is not None else None,
        active_swing_high=active_high,
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(hours=1) if active_high is not None else None,
        range_width=Decimal("1.2") if active_low is not None else None,
        equilibrium=Decimal("10.4") if active_low is not None else None,
        equilibrium_band_low=Decimal("10.34") if active_low is not None else None,
        equilibrium_band_high=Decimal("10.46") if active_low is not None else None,
        zone_location=zone_location if active_low is not None else "NO_VALID_RANGE",
        distance_from_equilibrium=Decimal("-0.2") if active_low is not None else None,
        distance_from_equilibrium_pct_of_range=Decimal("-0.1667") if active_low is not None else None,
    )


def _pattern_result(bar: EngineBar, *, reclaim: str = "NONE", fake_breakdown: str = "NONE", recontainment: str = "NONE") -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
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
        bullish_reclaim=LifecyclePatternResult(reclaim, Decimal("9.8") if reclaim != "NONE" else None, bar.bar_timestamp - timedelta(minutes=20) if reclaim != "NONE" else None, None, None, None),
        bullish_fake_breakdown=LifecyclePatternResult(fake_breakdown, Decimal("9.8") if fake_breakdown != "NONE" else None, bar.bar_timestamp - timedelta(minutes=20) if fake_breakdown != "NONE" else None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("NONE", None, None, None, None),
        recontainment=RecontainmentResult(recontainment, None, None, None, Decimal("9.8"), Decimal("11.0")),
        events_on_bar=[],
        active_flags=[],
    )


def _frame_input(name: str, bar: EngineBar, structure_history: list[StructureEngineResult], zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(
        timeframe=name,
        latest_bar=bar,
        structure=structure_history[-1],
        structure_history=structure_history,
        zone=zone,
        pattern=pattern,
    )


def _signal_input(
    *,
    htf_history: list[StructureEngineResult],
    htf_zone: ZoneEngineResult,
    mtf_history: list[StructureEngineResult],
    mtf_zone: ZoneEngineResult,
    mtf_pattern: PatternEngineResult,
    ltf_history: list[StructureEngineResult],
    ltf_zone: ZoneEngineResult,
    ltf_pattern: PatternEngineResult,
) -> SignalEngineInput:
    symbol_id = htf_history[-1].symbol_id
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, htf_history[-1].bar_timestamp, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, mtf_history[-1].bar_timestamp, "10.5")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ltf_history[-1].bar_timestamp, "10.5")
    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=[],
        universe_known_at=htf_history[-1].known_at,
        htf=_frame_input("4H", htf_bar, htf_history, htf_zone, _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_history, mtf_zone, mtf_pattern),
        ltf=_frame_input("15M", ltf_bar, ltf_history, ltf_zone, ltf_pattern),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_history[-1].known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_history[-1].known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_history[-1].known_at),
    )


def test_htf_no_valid_range_without_bearish_evidence_is_neutral() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    htf_history = [_structure_result(htf_bar, trend_state="UNDEFINED")]
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.5")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.5")
    signal_input = _signal_input(
        htf_history=htf_history,
        htf_zone=_zone_result(htf_bar, range_status="NO_VALID_RANGE"),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="CANDIDATE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ts, ts, Decimal("10.4"), Decimal("10.5"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.bias_htf == "NEUTRAL"
    assert "HTF_UNCLEAR" in result.reason_codes


def test_htf_recent_bearish_event_is_bearish() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    htf_bar_old = _bar(symbol_id, Timeframe.HOUR_4, ts - timedelta(hours=4), "10.2")
    htf_bar_new = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.1")
    bearish_event = StructureEvent("BEARISH_BOS", htf_bar_old.bar_timestamp, htf_bar_old.bar_timestamp, Decimal("9.8"), Decimal("9.7"))
    htf_history = [
        _structure_result(htf_bar_old, trend_state="UNDEFINED", events=[bearish_event]),
        _structure_result(htf_bar_new, trend_state="UNDEFINED"),
    ]
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.1")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.1")
    signal_input = _signal_input(
        htf_history=htf_history,
        htf_zone=_zone_result(htf_bar_new),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="CANDIDATE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_BOS", ts, ts, Decimal("10.0"), Decimal("10.1"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.bias_htf == "BEARISH"
    assert result.reason_codes[2] == "HTF_BEARISH"


def test_mtf_recent_bearish_event_invalidates_with_lookback_window() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar_prev = _bar(symbol_id, Timeframe.HOUR_1, ts - timedelta(hours=1), "10.0")
    mtf_bar_now = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.1")
    bearish_event = StructureEvent("BEARISH_CHOCH", mtf_bar_prev.bar_timestamp, mtf_bar_prev.bar_timestamp, Decimal("9.9"), Decimal("9.8"))
    mtf_history = [
        _structure_result(mtf_bar_prev, events=[bearish_event]),
        _structure_result(mtf_bar_now),
    ]
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.1")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=mtf_history,
        mtf_zone=_zone_result(mtf_bar_now),
        mtf_pattern=_pattern_result(mtf_bar_now, recontainment="CANDIDATE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ts, ts, Decimal("10.0"), Decimal("10.1"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    result = SignalEngine(SignalEngineConfig(mtf_invalidation_lookback_bars=2)).evaluate(signal_input)

    assert result.extensible_context["internal_mtf_state"] == "INVALIDATED"
    assert result.setup_state == "INVALIDATED"


def test_internal_mtf_state_stays_distinct_from_output_setup_state() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ts, ts, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.extensible_context["internal_mtf_state"] == "RECONTAINMENT_CANDIDATE"
    assert result.setup_state == "RECONTAINMENT_CONFIRMED"
