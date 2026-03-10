from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import EngineBar, StructureEngineResult, StructureReferenceLevels
from doctrine_engine.engines.structure_engine import StructureEngine, StructureEngineConfig
from doctrine_engine.engines.zone_engine import ZoneEngine, ZoneEngineConfig


def _bars(rows: list[tuple[str, str, str, str]]) -> list[EngineBar]:
    symbol_id = uuid.uuid4()
    start = datetime(2026, 1, 7, 14, 30, tzinfo=timezone.utc)
    return [
        EngineBar(
            symbol_id=symbol_id,
            timeframe=Timeframe.MIN_5,
            bar_timestamp=start + timedelta(minutes=5 * index),
            known_at=start + timedelta(minutes=5 * index + 15),
            open_price=Decimal(open_price),
            high_price=Decimal(high_price),
            low_price=Decimal(low_price),
            close_price=Decimal(close_price),
        )
        for index, (open_price, high_price, low_price, close_price) in enumerate(rows)
    ]


def test_bos_anchored_range_selection_wins_when_bos_exists() -> None:
    bars = _bars(
        [
            ("9.8", "10.0", "9.2", "9.6"),
            ("9.7", "12.0", "9.7", "11.7"),
            ("11.3", "10.9", "8.0", "8.4"),
            ("8.7", "10.1", "8.6", "9.7"),
            ("12.3", "12.6", "11.8", "12.4"),
        ]
    )

    structure_result = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate(bars)
    zone_result = ZoneEngine().evaluate(bars, structure_result)

    assert structure_result.active_range_selection == "BOS_ANCHORED"
    assert zone_result.selection_reason == "BOS_ANCHORED"
    assert zone_result.active_swing_low == Decimal("8.0")
    assert zone_result.active_swing_high == Decimal("12.0")


def test_bracketing_pair_and_latest_pair_fallback_are_selected_deterministically() -> None:
    bracket_bars = _bars(
        [
            ("9.6", "10.0", "9.3", "9.8"),
            ("9.9", "12.0", "9.9", "11.3"),
            ("11.0", "10.8", "8.0", "8.5"),
            ("8.7", "11.0", "8.6", "9.7"),
            ("9.8", "10.4", "9.4", "9.9"),
        ]
    )
    structure_engine = StructureEngine(StructureEngineConfig(pivot_window=1))
    zone_engine = ZoneEngine()

    bracket_structure = structure_engine.evaluate(bracket_bars)
    bracket_zone = zone_engine.evaluate(bracket_bars, bracket_structure)
    assert bracket_zone.selection_reason == "BRACKETING_PAIR"

    fallback_bars = _bars(
        [
            ("10.0", "10.2", "9.5", "10.0"),
            ("9.9", "10.1", "8.0", "8.4"),
            ("8.5", "12.0", "8.4", "11.4"),
            ("11.6", "13.4", "11.2", "13.1"),
        ]
    )
    fallback_structure = StructureEngineResult(
        symbol_id=fallback_bars[-1].symbol_id,
        timeframe=fallback_bars[-1].timeframe,
        bar_timestamp=fallback_bars[-1].bar_timestamp,
        known_at=fallback_bars[-1].known_at,
        config_version="v1",
        pivot_window=1,
        swing_points=[],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=None,
            bullish_bos_reference_timestamp=None,
            bullish_bos_protected_low_price=None,
            bullish_bos_protected_low_timestamp=None,
            bearish_bos_reference_price=None,
            bearish_bos_reference_timestamp=None,
            bearish_bos_protected_high_price=None,
            bearish_bos_protected_high_timestamp=None,
            bullish_choch_reference_price=None,
            bullish_choch_reference_timestamp=None,
            bearish_choch_reference_price=None,
            bearish_choch_reference_timestamp=None,
        ),
        active_range_selection="LATEST_PAIR_FALLBACK",
        active_range_low=Decimal("8.0"),
        active_range_low_timestamp=fallback_bars[1].bar_timestamp,
        active_range_high=Decimal("12.0"),
        active_range_high_timestamp=fallback_bars[2].bar_timestamp,
        trend_state="UNDEFINED",
        events_on_bar=[],
    )
    fallback_zone = zone_engine.evaluate(fallback_bars, fallback_structure)
    assert fallback_zone.selection_reason == "LATEST_PAIR_FALLBACK"


def test_no_valid_range_and_equilibrium_band_boundaries() -> None:
    no_range_bars = _bars(
        [
            ("9.8", "10.2", "9.7", "10.0"),
            ("10.0", "10.1", "9.8", "9.9"),
        ]
    )
    structure_engine = StructureEngine(StructureEngineConfig(pivot_window=1))
    zone_engine = ZoneEngine(ZoneEngineConfig(equilibrium_band_ratio=Decimal("0.10")))

    no_range_structure = structure_engine.evaluate(no_range_bars)
    no_range_zone = zone_engine.evaluate(no_range_bars, no_range_structure)
    assert no_range_zone.range_status == "NO_VALID_RANGE"
    assert no_range_zone.zone_location == "NO_VALID_RANGE"

    bars = _bars(
        [
            ("10.0", "10.2", "9.5", "10.0"),
            ("9.9", "10.1", "8.0", "8.4"),
            ("8.5", "12.0", "8.4", "11.4"),
            ("11.0", "11.2", "9.8", "10.0"),
        ]
    )
    structure_result = structure_engine.evaluate(bars)
    zone_result = zone_engine.evaluate(bars, structure_result)

    assert zone_result.zone_location == "EQUILIBRIUM"
