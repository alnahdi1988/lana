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
    start = datetime(2026, 1, 9, 14, 30, tzinfo=timezone.utc)
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


def _structure_result(
    bar: EngineBar,
    bars: list[EngineBar],
    events_on_bar: list[StructureEvent] | None = None,
    bullish_bos_reference_price: Decimal | None = Decimal("10.0"),
) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        pivot_window=1,
        swing_points=[
            SwingPoint("LOW", bars[0].bar_timestamp, bars[1].bar_timestamp, Decimal("10.0"), 0),
            SwingPoint("HIGH", bars[1].bar_timestamp, bars[2].bar_timestamp, Decimal("12.0"), 1),
            SwingPoint("LOW", bars[2].bar_timestamp, bars[3].bar_timestamp if len(bars) > 3 else bars[-1].bar_timestamp, Decimal("10.2"), 2),
            SwingPoint("HIGH", bars[3].bar_timestamp if len(bars) > 3 else bars[-1].bar_timestamp, bars[4].bar_timestamp if len(bars) > 4 else bars[-1].bar_timestamp, Decimal("11.8"), 3),
        ],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=bullish_bos_reference_price,
            bullish_bos_reference_timestamp=bars[1].bar_timestamp if bullish_bos_reference_price is not None else None,
            bullish_bos_protected_low_price=Decimal("10.0") if bullish_bos_reference_price is not None else None,
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
        active_range_low=Decimal("10.0"),
        active_range_low_timestamp=bars[0].bar_timestamp,
        active_range_high=Decimal("12.0"),
        active_range_high_timestamp=bars[1].bar_timestamp,
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=events_on_bar or [],
    )


def _zone_result(
    bar: EngineBar,
    bars: list[EngineBar],
    zone_location: str = "EQUILIBRIUM",
    range_status: str = "RANGE_AVAILABLE",
) -> ZoneEngineResult:
    return ZoneEngineResult(
        symbol_id=bar.symbol_id,
        timeframe=bar.timeframe,
        bar_timestamp=bar.bar_timestamp,
        known_at=bar.known_at,
        config_version="v1",
        range_status=range_status,
        selection_reason="BRACKETING_PAIR" if range_status == "RANGE_AVAILABLE" else "NO_VALID_RANGE",
        active_swing_low=Decimal("10.0") if range_status == "RANGE_AVAILABLE" else None,
        active_swing_low_timestamp=bars[0].bar_timestamp if range_status == "RANGE_AVAILABLE" else None,
        active_swing_high=Decimal("12.0") if range_status == "RANGE_AVAILABLE" else None,
        active_swing_high_timestamp=bars[1].bar_timestamp if range_status == "RANGE_AVAILABLE" else None,
        range_width=Decimal("2.0") if range_status == "RANGE_AVAILABLE" else None,
        equilibrium=Decimal("11.0") if range_status == "RANGE_AVAILABLE" else None,
        equilibrium_band_low=Decimal("10.9") if range_status == "RANGE_AVAILABLE" else None,
        equilibrium_band_high=Decimal("11.1") if range_status == "RANGE_AVAILABLE" else None,
        zone_location=zone_location if range_status == "RANGE_AVAILABLE" else "NO_VALID_RANGE",
        distance_from_equilibrium=bar.close_price - Decimal("11.0") if range_status == "RANGE_AVAILABLE" else None,
        distance_from_equilibrium_pct_of_range=(bar.close_price - Decimal("11.0")) / Decimal("2.0") if range_status == "RANGE_AVAILABLE" else None,
    )


def test_reclaim_lifecycle_transitions_from_candidate_to_invalidation() -> None:
    bars = _bars(
        [
            ("10.4", "10.8", "10.2", "10.5"),
            ("10.5", "10.6", "9.8", "9.9"),
            ("10.0", "10.4", "10.0", "10.2"),
            ("10.2", "10.4", "10.1", "10.1"),
            ("10.1", "10.5", "10.0", "10.3"),
            ("10.2", "10.2", "9.7", "9.8"),
        ]
    )
    structure_history = [_structure_result(bar, bars, bullish_bos_reference_price=None) for bar in bars]
    zone_history = [_zone_result(bar, bars) for bar in bars]
    engine = PatternEngine(PatternEngineConfig(atr_period=20))

    history = engine.evaluate_history(bars, structure_history=structure_history, zone_history=zone_history)

    assert history[1].bullish_reclaim.status == "CANDIDATE"
    assert history[3].bullish_reclaim.status == "NEW_EVENT"
    assert history[4].bullish_reclaim.status == "ACTIVE"
    assert history[5].bullish_reclaim.status == "INVALIDATED"


def test_fake_breakdown_and_trap_reverse_preserve_same_bar_event_order() -> None:
    bars = _bars(
        [
            ("10.4", "10.8", "10.2", "10.5"),
            ("10.5", "10.7", "9.8", "9.9"),
            ("10.0", "10.5", "9.9", "10.2"),
            ("10.2", "10.5", "10.1", "10.1"),
        ]
    )
    structure_history = [
        _structure_result(bar, bars, bullish_bos_reference_price=Decimal("10.0"))
        for bar in bars
    ]
    structure_history[3] = _structure_result(
        bars[3],
        bars,
        events_on_bar=[
            StructureEvent(
                event_type="BULLISH_CHOCH",
                event_timestamp=bars[3].bar_timestamp,
                reference_timestamp=bars[1].bar_timestamp,
                reference_price=Decimal("10.8"),
                close_price=bars[3].close_price,
            )
        ],
        bullish_bos_reference_price=Decimal("10.0"),
    )
    zone_history = [_zone_result(bar, bars, zone_location="EQUILIBRIUM") for bar in bars]
    engine = PatternEngine(PatternEngineConfig(atr_period=1))

    history = engine.evaluate_history(bars, structure_history=structure_history, zone_history=zone_history)

    assert history[2].bullish_fake_breakdown.status == "NEW_EVENT"
    assert history[3].bullish_reclaim.status == "NEW_EVENT"
    assert history[3].bullish_trap_reverse.status == "NEW_EVENT"
    assert [event.event_type for event in history[3].events_on_bar] == [
        "BULLISH_RECLAIM",
        "BULLISH_TRAP_REVERSE",
    ]


def test_recontainment_is_timeframe_local_and_invalidates_when_zone_has_no_valid_range() -> None:
    bars = _bars(
        [
            ("9.8", "10.0", "9.7", "9.9"),
            ("9.9", "10.1", "9.8", "10.0"),
            ("10.0", "12.7", "9.9", "12.5"),
            ("11.5", "11.7", "10.6", "10.8"),
            ("10.8", "10.9", "10.5", "10.7"),
        ]
    )
    structure_history = [_structure_result(bar, bars, bullish_bos_reference_price=Decimal("10.0")) for bar in bars]
    zone_history = [
        _zone_result(bars[0], bars),
        _zone_result(bars[1], bars),
        _zone_result(bars[2], bars, zone_location="PREMIUM"),
        _zone_result(bars[3], bars, zone_location="DISCOUNT"),
        _zone_result(bars[4], bars, range_status="NO_VALID_RANGE"),
    ]
    engine = PatternEngine(PatternEngineConfig(atr_period=2))

    history = engine.evaluate_history(bars, structure_history=structure_history, zone_history=zone_history)

    assert history[3].recontainment.status == "ACTIVE"
    assert any(event.event_type == "RECONTAINMENT_ENTERED" for event in history[3].events_on_bar)
    assert history[4].recontainment.status == "INVALIDATED"
    assert all(event.event_type != "RECONTAINMENT_ENTERED" for event in history[4].events_on_bar)
