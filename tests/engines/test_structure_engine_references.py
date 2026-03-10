from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import EngineBar
from doctrine_engine.engines.structure_engine import StructureEngine, StructureEngineConfig


def _bars(rows: list[tuple[str, str, str, str]]) -> list[EngineBar]:
    symbol_id = uuid.uuid4()
    start = datetime(2026, 1, 6, 14, 30, tzinfo=timezone.utc)
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


def test_gap_through_close_bullish_bos_emits_once_on_first_qualifying_close() -> None:
    bars = _bars(
        [
            ("9.8", "10.0", "9.2", "9.6"),
            ("9.7", "12.0", "9.7", "11.7"),
            ("11.3", "10.9", "8.0", "8.4"),
            ("8.7", "10.1", "8.6", "9.7"),
            ("12.3", "12.6", "11.8", "12.4"),
            ("12.4", "12.8", "12.0", "12.5"),
        ]
    )

    history = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate_history(bars)
    bos_events = [event for result in history for event in result.events_on_bar if event.event_type == "BULLISH_BOS"]

    assert len(bos_events) == 1
    assert bos_events[0].event_timestamp == bars[4].bar_timestamp
    assert history[-1].reference_levels.bullish_bos_reference_price is None


def test_wick_only_break_does_not_emit_bullish_bos() -> None:
    bars = _bars(
        [
            ("9.8", "10.0", "9.2", "9.6"),
            ("9.7", "12.0", "9.7", "11.7"),
            ("11.3", "10.9", "8.0", "8.4"),
            ("8.7", "10.1", "8.6", "9.7"),
            ("11.8", "12.5", "11.1", "11.9"),
        ]
    )

    result = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate(bars)

    assert all(event.event_type != "BULLISH_BOS" for event in result.events_on_bar)
    assert result.reference_levels.bullish_bos_reference_price == Decimal("12.0")


def test_bullish_choch_uses_lower_high_reference() -> None:
    bars = _bars(
        [
            ("10.0", "10.4", "9.4", "10.0"),
            ("10.1", "14.0", "10.0", "13.4"),
            ("13.0", "11.0", "8.0", "8.6"),
            ("8.8", "13.0", "9.0", "12.7"),
            ("12.1", "10.2", "7.0", "7.4"),
            ("13.1", "13.4", "8.7", "13.1"),
        ]
    )

    result = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate(bars)

    assert result.reference_levels.bullish_choch_reference_price == Decimal("13.0")
    assert any(event.event_type == "BULLISH_CHOCH" for event in result.events_on_bar)
