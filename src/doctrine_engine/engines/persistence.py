from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from doctrine_engine.db.models.features import Feature
from doctrine_engine.engines.models import PatternEngineResult, StructureEngineResult, ZoneEngineResult

FEATURE_SET_STRUCTURE = "STRUCTURE_ENGINE"
FEATURE_SET_ZONE = "ZONE_ENGINE"
FEATURE_SET_PATTERN = "PATTERN_ENGINE"
FEATURE_VERSION_V1 = "v1"
FEATURE_UNIQUENESS_BOUNDARY = (
    "symbol_id",
    "timeframe",
    "feature_set",
    "feature_version",
    "bar_timestamp",
)


def build_feature_row(result: StructureEngineResult | ZoneEngineResult | PatternEngineResult) -> dict[str, Any]:
    feature_set = _feature_set_for_result(result)
    return {
        "symbol_id": result.symbol_id,
        "timeframe": result.timeframe,
        "feature_set": feature_set,
        "feature_version": FEATURE_VERSION_V1,
        "bar_timestamp": result.bar_timestamp,
        "known_at": result.known_at,
        "values": _serialize(result),
    }


def build_feature_upsert_statement(result: StructureEngineResult | ZoneEngineResult | PatternEngineResult):
    row = build_feature_row(result)
    statement = insert(Feature).values(**row)
    return statement.on_conflict_do_update(
        index_elements=list(FEATURE_UNIQUENESS_BOUNDARY),
        set_={
            "known_at": statement.excluded.known_at,
            "values": statement.excluded["values"],
            "updated_at": func.now(),
        },
    )


def upsert_feature_result(
    session: Session,
    result: StructureEngineResult | ZoneEngineResult | PatternEngineResult,
) -> None:
    session.execute(build_feature_upsert_statement(result))


def _feature_set_for_result(result: StructureEngineResult | ZoneEngineResult | PatternEngineResult) -> str:
    if isinstance(result, StructureEngineResult):
        return FEATURE_SET_STRUCTURE
    if isinstance(result, ZoneEngineResult):
        return FEATURE_SET_ZONE
    if isinstance(result, PatternEngineResult):
        return FEATURE_SET_PATTERN
    raise TypeError(f"Unsupported feature result type: {type(result)!r}")


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value
