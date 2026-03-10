from __future__ import annotations

import uuid
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


def _bar(symbol_id: uuid.UUID, timeframe: Timeframe, ts: datetime, close: str, known_offset: int) -> EngineBar:
    close_price = Decimal(close)
    return EngineBar(symbol_id, timeframe, ts, ts + timedelta(minutes=known_offset), close_price, close_price + Decimal("0.20"), close_price - Decimal("0.20"), close_price)


def _structure_result(bar: EngineBar, *, low: str, high: str) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(hours=2), bar.bar_timestamp - timedelta(hours=1), Decimal(low), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(hours=1), bar.bar_timestamp, Decimal(high), 1),
        ],
        reference_levels=StructureReferenceLevels(Decimal(high), bar.bar_timestamp - timedelta(hours=1), Decimal(low), bar.bar_timestamp - timedelta(hours=2), Decimal(low), bar.bar_timestamp - timedelta(hours=2), Decimal(high), bar.bar_timestamp - timedelta(hours=1), None, None, None, None),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal(low),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(hours=2),
        active_range_high=Decimal(high),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(hours=1),
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=[StructureEvent("BULLISH_CHOCH", bar.bar_timestamp, bar.bar_timestamp - timedelta(minutes=15), Decimal("10.70"), Decimal("10.65"))] if bar.timeframe == Timeframe.MIN_15 else [],
    )


def _zone_result(bar: EngineBar, *, low: str, high: str, eq: str, eq_low: str, eq_high: str) -> ZoneEngineResult:
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
        zone_location="DISCOUNT",
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
        bullish_displacement=DisplacementResult("ACTIVE", "SINGLE_BAR", bar.bar_timestamp, Decimal("10.30"), bar.bar_timestamp, Decimal("1.7"), Decimal("0.82")),
        bullish_reclaim=LifecyclePatternResult("ACTIVE", Decimal("10.00"), bar.bar_timestamp - timedelta(minutes=20), None, None, bar.bar_timestamp - timedelta(minutes=5)),
        bullish_fake_breakdown=LifecyclePatternResult("NONE", None, None, None, None, None),
        bullish_trap_reverse=TrapReverseResult("ACTIVE", Decimal("9.95"), bar.bar_timestamp - timedelta(minutes=30), "BULLISH_CHOCH", bar.bar_timestamp - timedelta(minutes=5)),
        recontainment=RecontainmentResult("ACTIVE", bar.bar_timestamp - timedelta(minutes=15), Decimal("10.20"), bar.bar_timestamp - timedelta(minutes=10), Decimal("9.80"), Decimal("11.10")),
        events_on_bar=[],
        active_flags=["BULLISH_RECLAIM", "BULLISH_TRAP_REVERSE", "RECONTAINMENT_ACTIVE"],
    )


def _frame_input(name: str, bar: EngineBar, structure: StructureEngineResult, zone: ZoneEngineResult, pattern: PatternEngineResult) -> SignalFrameInput:
    return SignalFrameInput(name, bar, structure, [structure], zone, pattern)


def test_plan_timestamp_and_known_at_are_preserved_from_signal_result() -> None:
    symbol_id = uuid.uuid4()
    htf_bar = _bar(symbol_id, Timeframe.HOUR_4, datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc), "11.10", 60)
    mtf_bar = _bar(symbol_id, Timeframe.HOUR_1, datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc), "10.75", 30)
    ltf_bar = _bar(symbol_id, Timeframe.MIN_15, datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc), "10.85", 15)

    signal_source = SignalEngineInput(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.85"),
        universe_reason_codes=[],
        universe_known_at=htf_bar.known_at,
        htf=_frame_input("4H", htf_bar, _structure_result(htf_bar, low="9.60", high="12.20"), _zone_result(htf_bar, low="9.60", high="12.20", eq="10.90", eq_low="10.60", eq_high="11.20"), _pattern_result(htf_bar)),
        mtf=_frame_input("1H", mtf_bar, _structure_result(mtf_bar, low="9.80", high="11.50"), _zone_result(mtf_bar, low="9.80", high="11.50", eq="10.65", eq_low="10.40", eq_high="10.90"), _pattern_result(mtf_bar)),
        ltf=_frame_input("15M", ltf_bar, _structure_result(ltf_bar, low="10.00", high="11.00"), _zone_result(ltf_bar, low="10.00", high="11.00", eq="10.50", eq_low="10.35", eq_high="10.65"), _pattern_result(ltf_bar)),
        micro=None,
        regime=SignalRegimeInput("BULLISH_TREND", "SECTOR_STRONG", Decimal("0.80"), Decimal("0.70"), True, True, [], htf_bar.known_at),
        event_risk=SignalEventRiskInput("NO_EVENT_RISK", False, True, Decimal("0.00"), [], htf_bar.known_at),
        sector_context=SignalSectorContextInput("NEUTRAL", None, [], htf_bar.known_at),
    )
    signal_result = SignalEngineResult(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        signal_timestamp=ltf_bar.bar_timestamp,
        known_at=ltf_bar.known_at,
        htf_bar_timestamp=htf_bar.bar_timestamp,
        mtf_bar_timestamp=mtf_bar.bar_timestamp,
        ltf_bar_timestamp=ltf_bar.bar_timestamp,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade="A",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=[],
        event_risk_blocked=False,
        extensible_context={"ltf_trigger_state": "TRAP_REVERSE_BULLISH"},
    )

    result = TradePlanEngine().build_plan(TradePlanEngineInput(uuid.uuid4(), signal_result, signal_source))

    assert result.plan_timestamp == signal_result.signal_timestamp
    assert result.known_at == signal_result.known_at
