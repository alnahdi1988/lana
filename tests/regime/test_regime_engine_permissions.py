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
    SignalRegimeInput,
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
    RegimeEngineConfig,
    RegimeEngineInput,
    RegimeIndexInput,
    SectorRegimeInput,
    StockRelativeRegimeInput,
    VolatilityInput,
)


def _bar(offset: int, known_offset_minutes: int = 15) -> EngineBar:
    ts = datetime(2026, 3, 10, 20, 0, tzinfo=timezone.utc) + timedelta(hours=offset)
    return EngineBar(uuid.uuid4(), Timeframe.DAY_1, ts, ts + timedelta(minutes=known_offset_minutes), Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100.5"))


def _structure(bar: EngineBar, trend_state: str, bearish_event: bool = False) -> StructureEngineResult:
    events = []
    if bearish_event:
        events.append(StructureEvent("BEARISH_BOS", bar.bar_timestamp, bar.bar_timestamp - timedelta(days=1), Decimal("99"), Decimal("98")))
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


def _index_input(ticker: str, *, trend_state: str = "BULLISH_SEQUENCE", bearish_event: bool = False, known_offset_minutes: int = 15) -> RegimeIndexInput:
    bar = _bar({"SPY": 0, "QQQ": 1, "IWM": 2}[ticker], known_offset_minutes=known_offset_minutes)
    structure = _structure(bar, trend_state, bearish_event=bearish_event)
    return RegimeIndexInput(ticker, bar, structure, _zone(bar), _pattern(bar), [structure])


def _sector_input(*, trend_state: str = "BULLISH_SEQUENCE", rs: Decimal | None = Decimal("0.03"), momentum: Decimal | None = Decimal("0.70"), known_offset_minutes: int = 15) -> SectorRegimeInput:
    bar = _bar(3, known_offset_minutes=known_offset_minutes)
    structure = _structure(bar, trend_state)
    return SectorRegimeInput("Technology", "XLK", bar, structure, _zone(bar), _pattern(bar), [structure], rs, momentum)


def _stock_relative(known_offset_minutes: int = 15, structure_quality_score: Decimal | None = Decimal("0.73")) -> StockRelativeRegimeInput:
    bar = _bar(4, known_offset_minutes=known_offset_minutes)
    return StockRelativeRegimeInput(bar.symbol_id, "TEST", "Technology", bar, Decimal("0.01"), Decimal("0.02"), structure_quality_score)


def _engine_input(*, market_indexes=None, sector=None, stock_relative=None, breadth=None, volatility=None) -> RegimeEngineInput:
    return RegimeEngineInput(
        market_indexes=market_indexes or [_index_input("SPY"), _index_input("QQQ"), _index_input("IWM")],
        sector=sector or _sector_input(),
        stock_relative=stock_relative or _stock_relative(),
        breadth=breadth,
        volatility=volatility,
    )


def test_permission_scores_are_clamped() -> None:
    result = RegimeEngine().evaluate(
        _engine_input(
            breadth=BreadthInput(Decimal("3.00"), Decimal("2.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("0.10"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert Decimal("0.0000") <= result.market_permission_score <= Decimal("1.0000")
    assert Decimal("0.0000") <= result.sector_permission_score <= Decimal("1.0000")


def test_allows_longs_false_in_risk_off() -> None:
    result = RegimeEngine().evaluate(
        _engine_input(
            market_indexes=[
                _index_input("SPY", trend_state="BEARISH_SEQUENCE"),
                _index_input("QQQ", trend_state="BEARISH_SEQUENCE"),
                _index_input("IWM", trend_state="MIXED", bearish_event=True),
            ],
            breadth=BreadthInput(Decimal("0.80"), Decimal("0.70"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.60"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "RISK_OFF"
    assert result.allows_longs is False


def test_weak_sector_and_low_market_permission_blocks_longs() -> None:
    result = RegimeEngine(
        RegimeEngineConfig(weak_sector_market_permission_block_threshold=Decimal("0.65"))
    ).evaluate(
        _engine_input(
            market_indexes=[_index_input("SPY", trend_state="MIXED"), _index_input("QQQ", trend_state="MIXED"), _index_input("IWM", trend_state="MIXED")],
            sector=_sector_input(trend_state="BEARISH_SEQUENCE", rs=Decimal("-0.03"), momentum=Decimal("0.20")),
            breadth=BreadthInput(Decimal("1.00"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.sector_regime == "SECTOR_WEAK"
    assert result.market_permission_score < Decimal("0.65")
    assert result.allows_longs is False


def test_missing_breadth_yields_partial_but_usable_result() -> None:
    result = RegimeEngine().evaluate(
        _engine_input(
            breadth=None,
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.coverage_complete is False
    assert result.reason_codes[-1] == "REGIME_PARTIAL_COVERAGE"


def test_missing_volatility_yields_partial_but_usable_result() -> None:
    result = RegimeEngine().evaluate(
        _engine_input(
            breadth=BreadthInput(Decimal("1.10"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=None,
        )
    )
    assert result.coverage_complete is False
    assert result.reason_codes[-1] == "REGIME_PARTIAL_COVERAGE"


def test_output_known_at_is_max_consumed_input_and_stock_quality_is_pass_through() -> None:
    stock_relative = _stock_relative(known_offset_minutes=45, structure_quality_score=Decimal("0.88"))
    result = RegimeEngine().evaluate(
        _engine_input(
            market_indexes=[
                _index_input("SPY", known_offset_minutes=10),
                _index_input("QQQ", known_offset_minutes=20),
                _index_input("IWM", known_offset_minutes=25),
            ],
            sector=_sector_input(known_offset_minutes=30),
            stock_relative=stock_relative,
            breadth=BreadthInput(Decimal("1.10"), Decimal("1.00"), datetime(2026, 3, 10, 21, 40, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 50, tzinfo=timezone.utc)),
        )
    )
    assert result.known_at == stock_relative.latest_bar.known_at
    assert result.stock_structure_quality_score == Decimal("0.88")


def test_result_maps_cleanly_into_signal_regime_input() -> None:
    result = RegimeEngine().evaluate(
        _engine_input(
            breadth=BreadthInput(Decimal("1.10"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    mapped = SignalRegimeInput(
        market_regime=result.market_regime,
        sector_regime=result.sector_regime,
        market_permission_score=result.market_permission_score,
        sector_permission_score=result.sector_permission_score,
        allows_longs=result.allows_longs,
        coverage_complete=result.coverage_complete,
        reason_codes=result.reason_codes,
        known_at=result.known_at,
    )
    assert mapped.market_regime == result.market_regime
    assert mapped.reason_codes == result.reason_codes
