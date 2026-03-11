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
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.regime.engine import RegimeEngine
from doctrine_engine.regime.models import (
    BreadthInput,
    RegimeEngineInput,
    RegimeIndexInput,
    SectorRegimeInput,
    StockRelativeRegimeInput,
    VolatilityInput,
)


def _bar(offset: int) -> EngineBar:
    ts = datetime(2026, 3, 10, 20, 0, tzinfo=timezone.utc) + timedelta(hours=offset)
    return EngineBar(uuid.uuid4(), Timeframe.DAY_1, ts, ts + timedelta(minutes=15), Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100.5"))


def _structure(bar: EngineBar, trend_state: str, bearish_event: bool = False) -> StructureEngineResult:
    events = []
    if bearish_event:
        events.append(StructureEvent("BEARISH_CHOCH", bar.bar_timestamp, bar.bar_timestamp - timedelta(days=1), Decimal("99"), Decimal("98.5")))
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(days=3), bar.bar_timestamp - timedelta(days=2), Decimal("95"), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(days=2), bar.bar_timestamp - timedelta(days=1), Decimal("105"), 1),
        ],
        reference_levels=StructureReferenceLevels(Decimal("105"), bar.bar_timestamp - timedelta(days=2), Decimal("95"), bar.bar_timestamp - timedelta(days=3), Decimal("95"), bar.bar_timestamp - timedelta(days=3), Decimal("105"), bar.bar_timestamp - timedelta(days=2), None, None, None, None),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("95"),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(days=3),
        active_range_high=Decimal("105"),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(days=2),
        trend_state=trend_state,
        events_on_bar=events,
    )


def _zone(bar: EngineBar) -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("95"),
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(days=3),
        active_swing_high=Decimal("105"),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(days=2),
        range_width=Decimal("10"),
        equilibrium=Decimal("100"),
        equilibrium_band_low=Decimal("99"),
        equilibrium_band_high=Decimal("101"),
        zone_location="EQUILIBRIUM",
        distance_from_equilibrium=Decimal("0.5"),
        distance_from_equilibrium_pct_of_range=Decimal("0.0500"),
    )


def _pattern(bar: EngineBar) -> PatternEngineResult:
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
        recontainment=RecontainmentResult("NONE", None, None, None, None, None),
        events_on_bar=[],
        active_flags=[],
    )


def _index_input(ticker: str) -> RegimeIndexInput:
    bar = _bar({"SPY": 0, "QQQ": 1, "IWM": 2}[ticker])
    structure = _structure(bar, "BULLISH_SEQUENCE")
    return RegimeIndexInput(ticker, bar, structure, _zone(bar), _pattern(bar), [structure])


def _sector_input(*, trend_state: str = "BULLISH_SEQUENCE", bearish_event: bool = False, rs: Decimal | None = Decimal("0.03"), momentum: Decimal | None = Decimal("0.70")) -> SectorRegimeInput:
    bar = _bar(3)
    structure = _structure(bar, trend_state, bearish_event=bearish_event)
    return SectorRegimeInput("Technology", "XLK", bar, structure, _zone(bar), _pattern(bar), [structure], rs, momentum)


def _stock_relative() -> StockRelativeRegimeInput:
    bar = _bar(4)
    return StockRelativeRegimeInput(bar.symbol_id, "TEST", "Technology", bar, Decimal("0.01"), Decimal("0.02"), Decimal("0.88"))


def _engine_input(sector: SectorRegimeInput) -> RegimeEngineInput:
    return RegimeEngineInput(
        market_indexes=[_index_input("SPY"), _index_input("QQQ"), _index_input("IWM")],
        sector=sector,
        stock_relative=_stock_relative(),
        breadth=BreadthInput(Decimal("1.00"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
        volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
    )


def test_bearish_sector_direction_is_weak() -> None:
    result = RegimeEngine().evaluate(_engine_input(_sector_input(trend_state="BEARISH_SEQUENCE")))
    assert result.sector_regime == "SECTOR_WEAK"
    assert result.reason_codes[1] == "SECTOR_WEAK"


def test_bullish_sector_plus_supportive_rs_is_strong() -> None:
    result = RegimeEngine().evaluate(_engine_input(_sector_input(rs=Decimal("0.03"), momentum=Decimal("0.50"))))
    assert result.sector_regime == "SECTOR_STRONG"


def test_bullish_sector_with_one_hostile_rs_is_not_weak_by_itself() -> None:
    result = RegimeEngine().evaluate(_engine_input(_sector_input(rs=Decimal("-0.03"), momentum=Decimal("0.55"))))
    assert result.sector_regime == "SECTOR_NEUTRAL"


def test_both_hostile_without_bullish_structure_is_weak() -> None:
    result = RegimeEngine().evaluate(_engine_input(_sector_input(trend_state="MIXED", rs=Decimal("-0.03"), momentum=Decimal("0.20"))))
    assert result.sector_regime == "SECTOR_WEAK"


def test_mixed_sector_signals_are_neutral() -> None:
    result = RegimeEngine().evaluate(_engine_input(_sector_input(trend_state="MIXED", rs=Decimal("0.00"), momentum=Decimal("0.50"))))
    assert result.sector_regime == "SECTOR_NEUTRAL"
