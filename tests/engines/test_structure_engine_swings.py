from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import EngineBar
from doctrine_engine.engines.structure_engine import StructureEngine, StructureEngineConfig


def _bars(rows: list[tuple[str, str, str, str]]) -> list[EngineBar]:
    symbol_id = uuid.uuid4()
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    bars: list[EngineBar] = []
    for index, (open_price, high_price, low_price, close_price) in enumerate(rows):
        bar_timestamp = start + timedelta(minutes=5 * index)
        bars.append(
            EngineBar(
                symbol_id=symbol_id,
                timeframe=Timeframe.MIN_5,
                bar_timestamp=bar_timestamp,
                known_at=bar_timestamp + timedelta(minutes=15),
                open_price=Decimal(open_price),
                high_price=Decimal(high_price),
                low_price=Decimal(low_price),
                close_price=Decimal(close_price),
            )
        )
    return bars


def test_equal_highs_do_not_form_swing_highs() -> None:
    bars = _bars(
        [
            ("9.5", "10.0", "9.0", "9.6"),
            ("9.8", "12.0", "9.4", "11.5"),
            ("11.3", "12.0", "9.5", "10.1"),
            ("10.2", "11.0", "9.6", "10.0"),
            ("9.9", "10.5", "9.1", "9.4"),
        ]
    )

    result = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate(bars)

    assert all(swing.kind != "HIGH" for swing in result.swing_points)


def test_equal_lows_do_not_form_swing_lows() -> None:
    bars = _bars(
        [
            ("10.2", "10.6", "9.0", "9.8"),
            ("9.9", "10.4", "8.0", "8.5"),
            ("8.6", "10.2", "8.0", "9.3"),
            ("9.3", "10.1", "8.4", "9.5"),
            ("9.4", "10.0", "8.6", "9.2"),
        ]
    )

    result = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate(bars)

    assert all(swing.kind != "LOW" for swing in result.swing_points)


def test_pivot_confirmation_is_delayed_and_trend_is_undefined_with_fewer_than_four_swings() -> None:
    bars = _bars(
        [
            ("9.8", "10.2", "9.5", "10.0"),
            ("10.0", "12.0", "9.8", "11.6"),
            ("11.0", "10.8", "8.0", "8.4"),
            ("8.5", "10.2", "8.6", "9.8"),
            ("9.9", "10.0", "9.0", "9.2"),
        ]
    )

    history = StructureEngine(StructureEngineConfig(pivot_window=1)).evaluate_history(bars)
    result = history[-1]

    assert len(result.swing_points) == 2
    assert result.swing_points[0].pivot_timestamp == bars[1].bar_timestamp
    assert result.swing_points[0].confirmed_at == bars[2].bar_timestamp
    assert result.swing_points[1].pivot_timestamp == bars[2].bar_timestamp
    assert result.swing_points[1].confirmed_at == bars[3].bar_timestamp
    assert result.trend_state == "UNDEFINED"
