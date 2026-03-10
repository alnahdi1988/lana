from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    EngineBar,
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    ZoneEngineResult,
)
from doctrine_engine.engines.pattern_engine import PatternEngine, PatternEngineConfig


def _bars(rows: list[tuple[str, str, str, str]]) -> list[EngineBar]:
    symbol_id = uuid.uuid4()
    start = datetime(2026, 1, 8, 14, 30, tzinfo=timezone.utc)
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


def _structure_history(
    bars: list[EngineBar],
    bullish_bos_reference_price: Decimal | None,
) -> list[StructureEngineResult]:
    swing_points = [
        SwingPoint("LOW", bars[0].bar_timestamp, bars[1].bar_timestamp, Decimal("9.0"), 0),
        SwingPoint("HIGH", bars[1].bar_timestamp, bars[2].bar_timestamp, Decimal("10.0"), 1),
        SwingPoint("LOW", bars[2].bar_timestamp, bars[3].bar_timestamp, Decimal("9.3"), 2),
        SwingPoint("HIGH", bars[3].bar_timestamp, bars[4].bar_timestamp if len(bars) > 4 else bars[-1].bar_timestamp, Decimal("9.8"), 3),
    ]
    history: list[StructureEngineResult] = []
    for bar in bars:
        history.append(
            StructureEngineResult(
                symbol_id=bar.symbol_id,
                timeframe=bar.timeframe,
                bar_timestamp=bar.bar_timestamp,
                known_at=bar.known_at,
                config_version="v1",
                pivot_window=1,
                swing_points=swing_points,
                reference_levels=StructureReferenceLevels(
                    bullish_bos_reference_price=bullish_bos_reference_price,
                    bullish_bos_reference_timestamp=bars[1].bar_timestamp if bullish_bos_reference_price is not None else None,
                    bullish_bos_protected_low_price=Decimal("9.0") if bullish_bos_reference_price is not None else None,
                    bullish_bos_protected_low_timestamp=bars[0].bar_timestamp if bullish_bos_reference_price is not None else None,
                    bearish_bos_reference_price=None,
                    bearish_bos_reference_timestamp=None,
                    bearish_bos_protected_high_price=None,
                    bearish_bos_protected_high_timestamp=None,
                    bullish_choch_reference_price=None,
                    bullish_choch_reference_timestamp=None,
                    bearish_choch_reference_price=None,
                    bearish_choch_reference_timestamp=None,
                ),
                active_range_selection="BRACKETING_PAIR",
                active_range_low=Decimal("9.0"),
                active_range_low_timestamp=bars[0].bar_timestamp,
                active_range_high=Decimal("10.0"),
                active_range_high_timestamp=bars[1].bar_timestamp,
                trend_state="BULLISH_SEQUENCE",
                events_on_bar=[],
            )
        )
    return history


def _zone_history(bars: list[EngineBar]) -> list[ZoneEngineResult]:
    history: list[ZoneEngineResult] = []
    for bar in bars:
        history.append(
            ZoneEngineResult(
                symbol_id=bar.symbol_id,
                timeframe=bar.timeframe,
                bar_timestamp=bar.bar_timestamp,
                known_at=bar.known_at,
                config_version="v1",
                range_status="RANGE_AVAILABLE",
                selection_reason="BRACKETING_PAIR",
                active_swing_low=Decimal("9.0"),
                active_swing_low_timestamp=bars[0].bar_timestamp,
                active_swing_high=Decimal("10.0"),
                active_swing_high_timestamp=bars[1].bar_timestamp,
                range_width=Decimal("1.0"),
                equilibrium=Decimal("9.5"),
                equilibrium_band_low=Decimal("9.45"),
                equilibrium_band_high=Decimal("9.55"),
                zone_location="EQUILIBRIUM",
                distance_from_equilibrium=bar.close_price - Decimal("9.5"),
                distance_from_equilibrium_pct_of_range=bar.close_price - Decimal("9.5"),
            )
        )
    return history


def test_missing_atr_produces_not_compressed_and_no_displacement() -> None:
    bars = _bars(
        [
            ("9.6", "9.9", "9.4", "9.6"),
            ("9.6", "9.8", "9.5", "9.6"),
            ("9.6", "9.8", "9.5", "9.6"),
            ("9.6", "9.8", "9.5", "9.6"),
        ]
    )
    engine = PatternEngine(PatternEngineConfig(atr_period=5))

    result = engine.evaluate(
        bars,
        structure_history=_structure_history(bars, Decimal("10.0")),
        zone_history=_zone_history(bars),
    )

    assert result.compression.status == "NOT_COMPRESSED"
    assert result.bullish_displacement.status == "NONE"
    assert not result.events_on_bar


def test_sequence_displacement_emits_once_and_suppresses_duplicate_same_reference() -> None:
    bars = _bars(
        [
            ("9.8", "10.0", "9.7", "9.9"),
            ("9.9", "10.1", "9.8", "10.0"),
            ("10.0", "10.2", "9.9", "10.0"),
            ("10.0", "12.6", "9.9", "12.4"),
            ("12.3", "12.9", "11.8", "12.7"),
        ]
    )
    engine = PatternEngine(PatternEngineConfig(atr_period=3, displacement_sequence_length=3))

    history = engine.evaluate_history(
        bars,
        structure_history=_structure_history(bars, Decimal("10.0")),
        zone_history=_zone_history(bars),
    )

    assert history[3].bullish_displacement.status == "NEW_EVENT"
    assert history[4].bullish_displacement.status == "ACTIVE"
    displacement_events = [
        event
        for result in history
        for event in result.events_on_bar
        if event.event_type == "BULLISH_DISPLACEMENT"
    ]
    assert len(displacement_events) == 1
