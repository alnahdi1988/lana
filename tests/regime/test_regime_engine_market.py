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
    PatternEvent,
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


def _bar(symbol_id: uuid.UUID, ticker_offset_hours: int) -> EngineBar:
    ts = datetime(2026, 3, 10, 20, 0, tzinfo=timezone.utc) + timedelta(hours=ticker_offset_hours)
    return EngineBar(
        symbol_id=symbol_id,
        timeframe=Timeframe.DAY_1,
        bar_timestamp=ts,
        known_at=ts + timedelta(minutes=15),
        open_price=Decimal("100.00"),
        high_price=Decimal("101.00"),
        low_price=Decimal("99.00"),
        close_price=Decimal("100.50"),
    )


def _structure(bar: EngineBar, trend_state: str, bearish_event: bool = False) -> StructureEngineResult:
    events = []
    if bearish_event:
        events.append(
            StructureEvent(
                "BEARISH_BOS",
                bar.bar_timestamp,
                bar.bar_timestamp - timedelta(days=1),
                Decimal("99.00"),
                Decimal("98.50"),
            )
        )
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=2,
        swing_points=[
            SwingPoint("LOW", bar.bar_timestamp - timedelta(days=4), bar.bar_timestamp - timedelta(days=3), Decimal("95.00"), 0),
            SwingPoint("HIGH", bar.bar_timestamp - timedelta(days=3), bar.bar_timestamp - timedelta(days=2), Decimal("105.00"), 1),
        ],
        reference_levels=StructureReferenceLevels(
            Decimal("105.00"),
            bar.bar_timestamp - timedelta(days=3),
            Decimal("95.00"),
            bar.bar_timestamp - timedelta(days=4),
            Decimal("95.00"),
            bar.bar_timestamp - timedelta(days=4),
            Decimal("105.00"),
            bar.bar_timestamp - timedelta(days=3),
            None,
            None,
            None,
            None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=Decimal("95.00"),
        active_range_low_timestamp=bar.bar_timestamp - timedelta(days=4),
        active_range_high=Decimal("105.00"),
        active_range_high_timestamp=bar.bar_timestamp - timedelta(days=3),
        trend_state=trend_state,
        events_on_bar=events,
    )


def _zone(bar: EngineBar, range_status: str = "RANGE_AVAILABLE") -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status=range_status,
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("95.00"),
        active_swing_low_timestamp=bar.bar_timestamp - timedelta(days=4),
        active_swing_high=Decimal("105.00"),
        active_swing_high_timestamp=bar.bar_timestamp - timedelta(days=3),
        range_width=Decimal("10.00"),
        equilibrium=Decimal("100.00"),
        equilibrium_band_low=Decimal("99.00"),
        equilibrium_band_high=Decimal("101.00"),
        zone_location="EQUILIBRIUM",
        distance_from_equilibrium=Decimal("0.50"),
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


def _index_input(ticker: str, *, trend_state: str = "BULLISH_SEQUENCE", bearish_event: bool = False) -> RegimeIndexInput:
    bar = _bar(uuid.uuid4(), {"SPY": 0, "QQQ": 1, "IWM": 2}[ticker])
    structure = _structure(bar, trend_state, bearish_event=bearish_event)
    return RegimeIndexInput(ticker, bar, structure, _zone(bar), _pattern(bar), [structure])


def _sector_input() -> SectorRegimeInput:
    bar = _bar(uuid.uuid4(), 3)
    structure = _structure(bar, "BULLISH_SEQUENCE")
    return SectorRegimeInput("Technology", "XLK", bar, structure, _zone(bar), _pattern(bar), [structure], Decimal("0.03"), Decimal("0.70"))


def _stock_relative() -> StockRelativeRegimeInput:
    bar = _bar(uuid.uuid4(), 4)
    return StockRelativeRegimeInput(bar.symbol_id, "TEST", "Technology", bar, Decimal("0.04"), Decimal("0.02"), Decimal("0.77"))


def _regime_input(*, spy=None, qqq=None, iwm=None, breadth=None, volatility=None) -> RegimeEngineInput:
    return RegimeEngineInput(
        market_indexes=[spy or _index_input("SPY"), qqq or _index_input("QQQ"), iwm or _index_input("IWM")],
        sector=_sector_input(),
        stock_relative=_stock_relative(),
        breadth=breadth,
        volatility=volatility,
    )


def test_bullish_trend_market_regime() -> None:
    result = RegimeEngine().evaluate(
        _regime_input(
            breadth=BreadthInput(Decimal("1.25"), Decimal("1.10"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.10"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "BULLISH_TREND"
    assert result.reason_codes[0] == "MARKET_BULLISH_TREND"


def test_high_vol_expansion_market_regime() -> None:
    result = RegimeEngine().evaluate(
        _regime_input(
            iwm=_index_input("IWM", trend_state="MIXED"),
            breadth=BreadthInput(Decimal("1.00"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.30"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "HIGH_VOL_EXPANSION"
    assert result.reason_codes[0] == "MARKET_HIGH_VOL_EXPANSION"


def test_weak_drift_market_regime() -> None:
    result = RegimeEngine().evaluate(
        _regime_input(
            qqq=_index_input("QQQ", trend_state="MIXED"),
            iwm=_index_input("IWM", trend_state="MIXED"),
            breadth=BreadthInput(Decimal("1.00"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "WEAK_DRIFT"


def test_chop_market_regime() -> None:
    result = RegimeEngine().evaluate(
        _regime_input(
            spy=_index_input("SPY", trend_state="MIXED"),
            qqq=_index_input("QQQ", trend_state="MIXED"),
            iwm=_index_input("IWM", trend_state="MIXED"),
            breadth=BreadthInput(Decimal("1.00"), Decimal("1.00"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.05"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "CHOP"


def test_risk_off_market_regime() -> None:
    result = RegimeEngine().evaluate(
        _regime_input(
            spy=_index_input("SPY", trend_state="BEARISH_SEQUENCE"),
            qqq=_index_input("QQQ", trend_state="BEARISH_SEQUENCE"),
            iwm=_index_input("IWM", trend_state="MIXED", bearish_event=True),
            breadth=BreadthInput(Decimal("0.80"), Decimal("0.70"), datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)),
            volatility=VolatilityInput(Decimal("1.00"), Decimal("1.60"), datetime(2026, 3, 10, 21, 5, tzinfo=timezone.utc)),
        )
    )
    assert result.market_regime == "RISK_OFF"
    assert result.reason_codes[0] == "MARKET_RISK_OFF"


def test_missing_required_index_raises_value_error() -> None:
    regime_input = _regime_input()
    bad_input = replace(regime_input, market_indexes=regime_input.market_indexes[:2])
    with pytest.raises(ValueError, match="SPY, QQQ, and IWM"):
        RegimeEngine().evaluate(bad_input)
