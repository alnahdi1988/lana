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
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.signal_engine import SignalEngine, SignalEngineConfig


def _bar(symbol_id: uuid.UUID, timeframe: Timeframe, ts: datetime, close: str, known_offset_minutes: int = 15) -> EngineBar:
    close_price = Decimal(close)
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=known_offset_minutes), close_price, close_price + Decimal("0.2"), close_price - Decimal("0.2"), close_price)


def _structure_result(bar: EngineBar, trend_state: str = "BULLISH_SEQUENCE") -> StructureEngineResult:
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
        trend_state=trend_state,
        events_on_bar=[],
    )


def _zone_result(bar: EngineBar, zone_location: str = "DISCOUNT") -> ZoneEngineResult:
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
        zone_location=zone_location,
        distance_from_equilibrium=Decimal("-0.2"),
        distance_from_equilibrium_pct_of_range=Decimal("-0.1667"),
    )


def _frame_input(name: str, bar: EngineBar, structure_history: list[StructureEngineResult], zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure_history[-1], structure_history, zone, pattern)


def _signal_input(*, htf_history, htf_zone, mtf_history, mtf_zone, mtf_pattern, ltf_history, ltf_zone, ltf_pattern) -> SignalEngineInput:
    symbol_id = htf_history[-1].symbol_id
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, htf_history[-1].bar_timestamp, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, mtf_history[-1].bar_timestamp, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ltf_history[-1].bar_timestamp, "10.4")
    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.50"),
        universe_reason_codes=[],
        universe_known_at=htf_history[-1].known_at,
        htf=_frame_input("4H", htf_bar, htf_history, htf_zone, _strong_pattern(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_history, mtf_zone, mtf_pattern),
        ltf=_frame_input("15M", ltf_bar, ltf_history, ltf_zone, ltf_pattern),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_history[-1].known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_history[-1].known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_history[-1].known_at),
    )


def _strong_pattern(bar):
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult(status="COMPRESSED", criteria_met=["RANGE_VS_ATR", "LEG_CONTRACTION", "NEAR_EQUILIBRIUM"], lookback_bars=5),
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.0"), bar.bar_timestamp - timedelta(minutes=15), Decimal("1.8"), Decimal("0.8")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), None, None, bar.bar_timestamp),
        bullish_fake_breakdown=LifecyclePatternResult("NONE", None, None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("ACTIVE", Decimal("9.8"), bar.bar_timestamp - timedelta(minutes=20), "BULLISH_CHOCH", bar.bar_timestamp),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=15), Decimal("10.0"), bar.bar_timestamp - timedelta(minutes=5), Decimal("9.8"), Decimal("11.0")),
        events_on_bar=[],
        active_flags=["COMPRESSION", "BULLISH_DISPLACEMENT", "BULLISH_RECLAIM", "BULLISH_TRAP_REVERSE", "RECONTAINMENT_ACTIVE"],
    )


def test_blocked_event_risk_with_high_confidence_structure_returns_none() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_strong_pattern(mtf_bar),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_strong_pattern(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        event_risk=SignalEventRiskInput("EARNINGS_BLOCK", True, True, Decimal("0.00"), ["EARNINGS_BLACKOUT_ACTIVE"], ts),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.signal == "NONE"
    assert result.grade == "IGNORE"
    assert result.event_risk_blocked is True
    assert result.reason_codes[7] == "EVENT_RISK_BLOCKED"


def test_regime_incomplete_fail_open_can_still_evaluate() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_strong_pattern(mtf_bar),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_strong_pattern(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        regime=SignalRegimeInput(None, None, None, None, None, False, [], ts),
        sector_context=SignalSectorContextInput("STRONG", None, [], ts),
    )

    result = SignalEngine().evaluate(signal_input)

    assert result.signal == "LONG"
    assert result.grade == "B"


def test_regime_incomplete_fail_closed_returns_none_and_ignore_grade() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar),
        mtf_pattern=_strong_pattern(mtf_bar),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_strong_pattern(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        regime=SignalRegimeInput(None, None, None, None, None, False, [], ts),
    )

    result = SignalEngine(SignalEngineConfig(fail_closed_regime=True)).evaluate(signal_input)

    assert result.signal == "NONE"
    assert result.grade == "IGNORE"
    assert result.reason_codes[6] == "REGIME_BLOCKED"


def test_confidence_formula_is_exact_and_price_out_of_range_forces_none() -> None:
    symbol_id = uuid.uuid4()
    ts = datetime(2026, 2, 3, 12, 0, tzinfo=timezone.utc)
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, ts, "10.5")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, ts, "10.3")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, ts, "10.4")
    signal_input = _signal_input(
        htf_history=[_structure_result(htf_bar)],
        htf_zone=_zone_result(htf_bar, zone_location="DISCOUNT"),
        mtf_history=[_structure_result(mtf_bar)],
        mtf_zone=_zone_result(mtf_bar, zone_location="DISCOUNT"),
        mtf_pattern=_strong_pattern(mtf_bar),
        ltf_history=[_structure_result(ltf_bar)],
        ltf_zone=_zone_result(ltf_bar),
        ltf_pattern=_strong_pattern(ltf_bar),
    )
    signal_input = replace(
        signal_input,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], ts),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.02"), [], ts),
        sector_context=SignalSectorContextInput("STRONG", None, [], ts),
    )

    long_result = SignalEngine().evaluate(signal_input)
    out_of_range_result = SignalEngine().evaluate(replace(signal_input, price_reference=Decimal("55.00")))

    assert long_result.confidence == Decimal("0.8100")
    assert long_result.signal == "LONG"
    assert long_result.grade == "A"
    assert out_of_range_result.signal == "NONE"
    assert out_of_range_result.grade == "IGNORE"
    assert out_of_range_result.reason_codes[0] == "PRICE_OUT_OF_RANGE"
