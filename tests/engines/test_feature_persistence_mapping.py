from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    StructureEngineResult,
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.persistence import (
    FEATURE_SET_PATTERN,
    FEATURE_SET_STRUCTURE,
    FEATURE_SET_ZONE,
    FEATURE_UNIQUENESS_BOUNDARY,
    FEATURE_VERSION_V1,
    build_feature_row,
    build_feature_upsert_statement,
)


def _timestamps() -> tuple[datetime, datetime]:
    bar_timestamp = datetime(2026, 1, 10, 14, 30, tzinfo=timezone.utc)
    return bar_timestamp, bar_timestamp


def _structure_result() -> StructureEngineResult:
    symbol_id = uuid.uuid4()
    bar_timestamp, known_at = _timestamps()
    return StructureEngineResult(
        symbol_id=symbol_id,
        timeframe=Timeframe.MIN_5,
        bar_timestamp=bar_timestamp,
        known_at=known_at,
        config_version="v1",
        pivot_window=1,
        swing_points=[SwingPoint("LOW", bar_timestamp, bar_timestamp, Decimal("9.5"), 0)],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=Decimal("10.0"),
            bullish_bos_reference_timestamp=bar_timestamp,
            bullish_bos_protected_low_price=Decimal("9.5"),
            bullish_bos_protected_low_timestamp=bar_timestamp,
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
        active_range_low=Decimal("9.5"),
        active_range_low_timestamp=bar_timestamp,
        active_range_high=Decimal("10.0"),
        active_range_high_timestamp=bar_timestamp,
        trend_state="UNDEFINED",
        events_on_bar=[],
    )


def _zone_result(symbol_id: uuid.UUID) -> ZoneEngineResult:
    bar_timestamp, known_at = _timestamps()
    return ZoneEngineResult(
        symbol_id=symbol_id,
        timeframe=Timeframe.MIN_5,
        bar_timestamp=bar_timestamp,
        known_at=known_at,
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=Decimal("9.5"),
        active_swing_low_timestamp=bar_timestamp,
        active_swing_high=Decimal("10.0"),
        active_swing_high_timestamp=bar_timestamp,
        range_width=Decimal("0.5"),
        equilibrium=Decimal("9.75"),
        equilibrium_band_low=Decimal("9.725"),
        equilibrium_band_high=Decimal("9.775"),
        zone_location="EQUILIBRIUM",
        distance_from_equilibrium=Decimal("0.00"),
        distance_from_equilibrium_pct_of_range=Decimal("0.00"),
    )


def _pattern_result(symbol_id: uuid.UUID) -> PatternEngineResult:
    bar_timestamp, known_at = _timestamps()
    return PatternEngineResult(
        symbol_id=symbol_id,
        timeframe=Timeframe.MIN_5,
        bar_timestamp=bar_timestamp,
        known_at=known_at,
        config_version="v1",
        compression=CompressionResult(status="NOT_COMPRESSED", criteria_met=[], lookback_bars=5),
        bullish_displacement=DisplacementResult(
            status="NONE",
            mode=None,
            event_timestamp=None,
            reference_price=None,
            reference_timestamp=None,
            range_multiple_atr=None,
            close_location_ratio=None,
        ),
        bullish_reclaim=LifecyclePatternResult(
            status="NONE",
            reference_price=None,
            reference_timestamp=None,
            sweep_low=None,
            candidate_start_timestamp=None,
            event_timestamp=None,
        ),
        bullish_fake_breakdown=LifecyclePatternResult(
            status="NONE",
            reference_price=None,
            reference_timestamp=None,
            sweep_low=None,
            candidate_start_timestamp=None,
            event_timestamp=None,
        ),
        bullish_trap_reverse=TrapReverseResult(
            status="NONE",
            reference_price=None,
            reference_timestamp=None,
            trigger_event=None,
            event_timestamp=None,
        ),
        recontainment=RecontainmentResult(
            status="NONE",
            source_displacement_timestamp=None,
            source_displacement_reference_price=None,
            candidate_start_timestamp=None,
            active_range_low=Decimal("9.5"),
            active_range_high=Decimal("10.0"),
        ),
        events_on_bar=[],
        active_flags=[],
    )


def test_feature_rows_use_exact_feature_sets_and_string_serialization() -> None:
    structure_result = _structure_result()
    zone_result = _zone_result(structure_result.symbol_id)
    pattern_result = _pattern_result(structure_result.symbol_id)

    structure_row = build_feature_row(structure_result)
    zone_row = build_feature_row(zone_result)
    pattern_row = build_feature_row(pattern_result)

    assert structure_row["feature_set"] == FEATURE_SET_STRUCTURE
    assert zone_row["feature_set"] == FEATURE_SET_ZONE
    assert pattern_row["feature_set"] == FEATURE_SET_PATTERN
    assert structure_row["feature_version"] == FEATURE_VERSION_V1
    assert structure_row["values"]["active_range_low"] == "9.5"
    assert structure_row["values"]["bar_timestamp"].endswith("Z")


def test_feature_upsert_targets_existing_uniqueness_boundary() -> None:
    statement = build_feature_upsert_statement(_structure_result())
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert FEATURE_UNIQUENESS_BOUNDARY == (
        "symbol_id",
        "timeframe",
        "feature_set",
        "feature_version",
        "bar_timestamp",
    )
    assert 'ON CONFLICT (symbol_id, timeframe, feature_set, feature_version, bar_timestamp)' in compiled
    assert 'known_at = excluded.known_at' in compiled
    assert 'values = excluded.values' in compiled
