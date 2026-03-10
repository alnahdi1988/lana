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
    return EngineBar(
        symbol_id=symbol_id,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts + timedelta(minutes=15),
        open_price=close_price,
        high_price=close_price + Decimal("0.30"),
        low_price=close_price - Decimal("0.30"),
        close_price=close_price,
    )


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
            None,
            None,
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


def _pattern_result(bar: EngineBar) -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        compression=CompressionResult("NOT_COMPRESSED", [], 5),
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.40"), bar.bar_timestamp, Decimal("1.8"), Decimal("0.8")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal("10.00"), bar.bar_timestamp - timedelta(minutes=30), Decimal("9.95"), bar.bar_timestamp - timedelta(minutes=15), bar.bar_timestamp - timedelta(minutes=5)),
        bullish_fake_breakdown=LifecyclePatternResult("ACTIVE", Decimal("9.95"), bar.bar_timestamp - timedelta(minutes=40), Decimal("9.90"), bar.bar_timestamp - timedelta(minutes=20), bar.bar_timestamp - timedelta(minutes=10)),
        bullish_trap_reverse=TrapReverseResult("ACTIVE", Decimal("9.92"), bar.bar_timestamp - timedelta(minutes=50), "BULLISH_CHOCH", bar.bar_timestamp - timedelta(minutes=5)),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=20), Decimal("10.25"), bar.bar_timestamp - timedelta(minutes=10), Decimal("9.80"), Decimal("11.20")),
        events_on_bar=[],
        active_flags=["BULLISH_DISPLACEMENT", "BULLISH_RECLAIM", "BULLISH_FAKE_BREAKDOWN", "BULLISH_TRAP_REVERSE", "RECONTAINMENT_ACTIVE"],
    )


def _frame_input(name: str, bar: EngineBar, structure: StructureEngineResult, zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure, [structure], zone, pattern)


def _signal_source(symbol_id: uuid.UUID) -> SignalEngineInput:
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc), "11.20")
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc), "10.60")
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc), "10.70")

    htf_structure = _structure_result(htf_bar, high="12.00", low="9.50")
    mtf_structure = _structure_result(mtf_bar, high="11.30", low="9.80")
    ltf_structure = _structure_result(
        ltf_bar,
        high="10.95",
        low="9.95",
        events_on_bar=[StructureEvent("BULLISH_CHOCH", ltf_bar.bar_timestamp, ltf_bar.bar_timestamp - timedelta(minutes=15), Decimal("10.80"), Decimal("10.90"))],
    )

    return SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.70"),
        universe_reason_codes=[],
        universe_known_at=htf_bar.known_at,
        htf=_frame_input("4H", htf_bar, htf_structure, _zone_result(htf_bar, low="9.50", high="12.00", eq="10.75", eq_low="10.55", eq_high="10.95"), _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, mtf_structure, _zone_result(mtf_bar, low="9.80", high="11.30", eq="10.55", eq_low="10.35", eq_high="10.75"), _pattern_result(mtf_bar)),
        ltf=_frame_input("15M", ltf_bar, ltf_structure, _zone_result(ltf_bar, low="9.95", high="10.95", eq="10.45", eq_low="10.25", eq_high="10.55"), _pattern_result(ltf_bar)),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_bar.known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_bar.known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_bar.known_at),
    )


def _signal_result(signal_source: SignalEngineInput, *, signal: str = "LONG", setup_state: str = "RECONTAINMENT_CONFIRMED", ltf_trigger_state: str = "TRAP_REVERSE_BULLISH") -> SignalEngineResult:
    return SignalEngineResult(
        symbol_id=signal_source.symbol_id,
        ticker=signal_source.ticker,
        universe_snapshot_id=signal_source.universe_snapshot_id,
        signal_timestamp=signal_source.ltf.latest_bar.bar_timestamp,
        known_at=signal_source.ltf.latest_bar.known_at,
        htf_bar_timestamp=signal_source.htf.latest_bar.bar_timestamp,
        mtf_bar_timestamp=signal_source.mtf.latest_bar.bar_timestamp,
        ltf_bar_timestamp=signal_source.ltf.latest_bar.bar_timestamp,
        signal=signal,
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade="A" if signal == "LONG" else "IGNORE",
        bias_htf="BULLISH",
        setup_state=setup_state,
        reason_codes=[],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": ltf_trigger_state},
    )


def test_signal_none_raises_even_if_setup_state_is_structurally_valid() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_result = _signal_result(signal_source, signal="NONE", setup_state="RECONTAINMENT_CONFIRMED")

    with pytest.raises(ValueError, match="LONG signal"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))


def test_symbol_and_timestamp_mismatches_raise() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_result = _signal_result(signal_source)

    bad_symbol_result = replace(signal_result, symbol_id=uuid.uuid4())
    with pytest.raises(ValueError, match="symbol_id"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), bad_symbol_result, signal_source))

    bad_timestamp_result = replace(signal_result, ltf_bar_timestamp=signal_result.ltf_bar_timestamp - timedelta(minutes=15))
    with pytest.raises(ValueError, match="LTF timestamps"):
        TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), bad_timestamp_result, signal_source))


def test_valid_long_input_builds_plan() -> None:
    signal_source = _signal_source(uuid.uuid4())
    signal_result = _signal_result(signal_source, setup_state="RECONTAINMENT_CONFIRMED", ltf_trigger_state="LTF_BULLISH_CHOCH")

    result = TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))

    assert result.ticker == "TEST"
    assert result.trail_mode == "STRUCTURAL"
