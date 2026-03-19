from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


FEATURE_SET_VERSION = "lifecycle_v1"
BASELINE_MODEL_NAME = "baseline_empirical_ranker"
MODEL_STATUS_TRAINED = "TRAINED"
MODEL_STATUS_VALIDATED = "VALIDATED"
MODEL_STATUS_PROMOTED = "PROMOTED"
MODEL_STATUS_REJECTED = "REJECTED"
MODEL_STATUS_FAILED = "FAILED"

NUMERIC_FEATURE_NAMES = (
    "confidence",
    "entry_width_pct",
    "confirmation_distance_pct",
    "invalidation_distance_pct",
    "tp1_rr",
    "tp2_rr",
    "bars_tracked",
)
CATEGORICAL_FEATURE_NAMES = (
    "grade",
    "setup_state",
    "bias_htf",
    "market_regime",
    "sector_regime",
    "event_risk_class",
    "micro_state",
    "entry_type",
    "alert_state",
)
BOOLEAN_FEATURE_NAMES = (
    "micro_present",
    "micro_used_for_confirmation",
    "telegram_sendable",
    "event_risk_blocked",
)


@dataclass(frozen=True, slots=True)
class LearningExample:
    signal_id: str
    ticker: str
    signal_timestamp: datetime
    known_at: datetime
    features: dict[str, Any]
    success_label: bool | None
    tp2_label: bool | None
    invalidated_first: bool | None
    mfe_pct: float | None
    mae_pct: float | None
    evaluation_status: str


@dataclass(frozen=True, slots=True)
class LearningDatasetSummary:
    dataset_version: str
    total_rows: int
    pending_rows: int
    finalized_rows: int
    labeled_rows: int
    positive_rows: int
    negative_rows: int


@dataclass(frozen=True, slots=True)
class ModelArtifactRecord:
    model_name: str
    model_version: str
    feature_set_version: str
    artifact_uri: str
    training_window_start: datetime
    training_window_end: datetime
    validation_window_start: datetime | None
    validation_window_end: datetime | None
    row_count: int
    params: dict[str, Any]
    metrics: dict[str, Any]


__all__ = [
    "BASELINE_MODEL_NAME",
    "BOOLEAN_FEATURE_NAMES",
    "CATEGORICAL_FEATURE_NAMES",
    "FEATURE_SET_VERSION",
    "LearningDatasetSummary",
    "LearningExample",
    "MODEL_STATUS_FAILED",
    "MODEL_STATUS_PROMOTED",
    "MODEL_STATUS_REJECTED",
    "MODEL_STATUS_TRAINED",
    "MODEL_STATUS_VALIDATED",
    "ModelArtifactRecord",
    "NUMERIC_FEATURE_NAMES",
]
