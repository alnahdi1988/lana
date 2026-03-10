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


def _structure_result(bar: EngineBar, trend_state: str = "BULLISH_SEQUENCE", events: list[StructureEvent] | None = None) -> StructureEngineResult:
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
        bullish_displacement=DisplacementResult("NONE", None, None, None, None, None, None),
        bullish_reclaim=LifecyclePatternResult(reclaim, Decimal("9.8") if reclaim != "NONE" else None, bar.bar_timestamp - timedelta(minutes=20) if reclaim != "NONE" else None, None, None, None),
        bullish_fake_breakdown=LifecyclePatternResult(fake_breakdown, Decimal("9.8") if fake_breakdown != "NONE" else None, bar.bar_timestamp - timedelta(minutes=20) if fake_breakdown != "NONE" else None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("NONE", None, None, None, None),
        recontainment=RecontainmentResult(recontainment, None, None, None, Decimal("9.8"), Decimal("11.0")),
        events_on_bar=[],
        active_flags=[],
    )


def _frame_input(name: str, bar: EngineBar, structure_history: list[StructureEngineResult], zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure_history[-1], structure_history, zone, pattern)


def _signal_input(*, htf_history, htf_zone, mtf_history, mtf_zone, mtf_pattern, ltf_history, ltf_zone, ltf_pattern) -> SignalEngineInput:
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


def test_ltf_trigger_priority_is_exact() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")

    ltf_pattern = _pattern_result(ltf_bar, reclaim="ACTIVE", fake_breakdown="ACTIVE")
    ltf_pattern = replace(
        ltf_pattern,
        bullish_trap_reverse=TrapReverseResult(
            "ACTIVE",
            Decimal("9.8"),
            ltf_bar.bar_timestamp - timedelta(minutes=20),
            "BULLISH_CHOCH",
            ltf_bar.bar_timestamp,
        ),
    )

    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=ltf_pattern,
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.extensible_context["ltf_trigger_state"] == "TRAP_REVERSE_BULLISH"
    assert result.reason_codes[4] == "TRAP_REVERSE_BULLISH"


def test_structure_trigger_freshness_window_applies_to_ltf_events() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_old = _bar(symbol_id, Timeframe.MIN_15, ts - timedelta(minutes=15), "10.1")
    ltf_new = _bar(symbol_id, Timeframe.MIN_15, ts, "10.2")
    old_event = StructureEvent("BULLISH_BOS", ltf_old.bar_timestamp, ltf_old.bar_timestamp, Decimal("10.0"), Decimal("10.1"))
    ltf_history = [_structure_result(ltf_old, events=[old_event]), _structure_result(ltf_new)]

    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=ltf_history,
        ltf_zone=_zone_result(ltf_new),
        ltf_pattern=_pattern_result(ltf_new),
    )

    stale_result = SignalEngine(SignalEngineConfig(ltf_structure_trigger_freshness_bars=1)).evaluate(signal_input)
    fresh_result = SignalEngine(SignalEngineConfig(ltf_structure_trigger_freshness_bars=2)).evaluate(signal_input)

    assert stale_result.extensible_context["ltf_trigger_state"] == "LTF_NO_TRIGGER"
    assert fresh_result.extensible_context["ltf_trigger_state"] == "LTF_BULLISH_BOS"


def test_alignment_requires_all_three_frames() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")

    aligned_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar, events=[StructureEvent("BULLISH_CHOCH", ts, ts, Decimal("10.2"), Decimal("10.4"))])],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )
    missing_ltf_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_pattern_result(mtf_bar, recontainment="ACTIVE"),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_pattern_result(ltf_bar),
    )

    aligned = SignalEngine().evaluate(aligned_input)
    missing = SignalEngine().evaluate(missing_ltf_input)

    assert aligned.reason_codes[5] == "CROSS_FRAME_ALIGNMENT"
    assert missing.reason_codes[4] == "LTF_NO_TRIGGER"
    assert missing.reason_codes[5] == "NO_CROSS_FRAME_CONFIRMATION"


def test_micro_required_and_missing_returns_none() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
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

    result = SignalEngine(SignalEngineConfig(require_micro_confirmation=True)).evaluate(signal_input)

    assert result.signal == "NONE"
    assert "MICRO_CONFIRMATION_MISSING" in result.reason_codes
