from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from doctrine_engine.learning.schemas import (
    BOOLEAN_FEATURE_NAMES,
    CATEGORICAL_FEATURE_NAMES,
    LearningExample,
    NUMERIC_FEATURE_NAMES,
)


def build_learning_example(row: Mapping[str, Any]) -> LearningExample:
    entry_zone_low = _decimal(row.get("entry_zone_low"))
    entry_zone_high = _decimal(row.get("entry_zone_high"))
    confirmation_level = _decimal(row.get("confirmation_level"))
    invalidation_level = _decimal(row.get("invalidation_level"))
    tp1 = _decimal(row.get("tp1"))
    tp2 = _decimal(row.get("tp2"))
    entry_reference = (entry_zone_low + entry_zone_high) / Decimal("2")
    entry_width = max(Decimal("0"), entry_zone_high - entry_zone_low)
    confirmation_distance = max(Decimal("0"), confirmation_level - entry_reference)
    invalidation_distance = max(Decimal("0"), entry_reference - invalidation_level)
    risk_distance = max(Decimal("0"), confirmation_level - invalidation_level)
    tp1_reward = max(Decimal("0"), tp1 - confirmation_level)
    tp2_reward = max(Decimal("0"), tp2 - confirmation_level)

    features: dict[str, Any] = {
        "confidence": _float(row.get("confidence")) or 0.0,
        "entry_width_pct": _pct(entry_width, entry_reference),
        "confirmation_distance_pct": _pct(confirmation_distance, entry_reference),
        "invalidation_distance_pct": _pct(invalidation_distance, entry_reference),
        "tp1_rr": _ratio(tp1_reward, risk_distance),
        "tp2_rr": _ratio(tp2_reward, risk_distance),
        "bars_tracked": int(row.get("bars_tracked") or 0),
        "grade": row.get("grade") or "UNKNOWN",
        "setup_state": row.get("setup_state") or "UNKNOWN",
        "bias_htf": row.get("bias_htf") or "UNKNOWN",
        "market_regime": row.get("market_regime") or "UNKNOWN",
        "sector_regime": row.get("sector_regime") or "UNKNOWN",
        "event_risk_class": row.get("event_risk_class") or "UNKNOWN",
        "micro_state": row.get("micro_state") or "UNKNOWN",
        "entry_type": row.get("entry_type") or "UNKNOWN",
        "alert_state": row.get("alert_state") or "UNKNOWN",
        "micro_present": bool(row.get("micro_present")),
        "micro_used_for_confirmation": bool(row.get("micro_used_for_confirmation")),
        "telegram_sendable": bool(row.get("telegram_sendable")),
        "event_risk_blocked": bool(row.get("event_risk_blocked")),
    }
    _assert_feature_shape(features)
    return LearningExample(
        signal_id=str(row["signal_id"]),
        ticker=str(row["ticker"]),
        signal_timestamp=_dt(row["signal_timestamp"]),
        known_at=_dt(row["known_at"]),
        features=features,
        success_label=_optional_bool(row.get("success_label")),
        tp2_label=_optional_bool(row.get("tp2_label")),
        invalidated_first=_optional_bool(row.get("invalidated_first")),
        mfe_pct=_float(row.get("mfe_pct")),
        mae_pct=_float(row.get("mae_pct")),
        evaluation_status=str(row.get("evaluation_status") or "UNKNOWN"),
    )


def to_feature_matrix(examples: list[LearningExample]) -> list[list[Any]]:
    ordered_names = list(NUMERIC_FEATURE_NAMES + CATEGORICAL_FEATURE_NAMES + BOOLEAN_FEATURE_NAMES)
    return [[example.features[name] for name in ordered_names] for example in examples]


def feature_column_names() -> list[str]:
    return list(NUMERIC_FEATURE_NAMES + CATEGORICAL_FEATURE_NAMES + BOOLEAN_FEATURE_NAMES)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _pct(distance: Decimal, reference: Decimal) -> float:
    if reference <= 0:
        return 0.0
    return float(((distance / reference) * Decimal("100")).quantize(Decimal("0.0001")))


def _ratio(reward: Decimal, risk: Decimal) -> float:
    if risk <= 0:
        return 0.0
    return float((reward / risk).quantize(Decimal("0.0001")))


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _assert_feature_shape(features: Mapping[str, Any]) -> None:
    expected = set(NUMERIC_FEATURE_NAMES + CATEGORICAL_FEATURE_NAMES + BOOLEAN_FEATURE_NAMES)
    missing = sorted(expected.difference(features))
    if missing:
        raise ValueError(f"Learning feature row missing fields: {missing}")


__all__ = ["build_learning_example", "feature_column_names", "to_feature_matrix"]
