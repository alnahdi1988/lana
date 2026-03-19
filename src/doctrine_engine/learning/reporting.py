from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from doctrine_engine.db.models.learning import ModelRun
from doctrine_engine.learning.registry import ModelRunRegistry
from doctrine_engine.learning.schemas import MODEL_STATUS_VALIDATED


@dataclass(frozen=True, slots=True)
class PromotionRecommendation:
    model_version: str
    recommendation: str
    reasons: list[str]
    validation_row_count: int


class BaselineRetrainer:
    def __init__(self, *, validator: Any) -> None:
        self.validator = validator

    def retrain(
        self,
        *,
        train_start,
        train_end,
        validate_start,
        validate_end,
        artifact_dir,
    ):
        return self.validator.validate(
            train_start=train_start,
            train_end=train_end,
            validate_start=validate_start,
            validate_end=validate_end,
            artifact_dir=artifact_dir,
            reuse_existing_training=False,
        )


class ValidationReporter:
    def __init__(self, *, registry: ModelRunRegistry) -> None:
        self.registry = registry

    def build(self, *, model_version: str) -> dict[str, Any]:
        row = self._require_row(model_version)
        recommendation = recommend_from_run(row)
        return {
            "model_name": row.model_name,
            "model_version": row.model_version,
            "feature_set_version": row.feature_set_version,
            "status": row.status,
            "promoted": row.promoted,
            "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
            "artifact_uri": row.artifact_uri,
            "training_window_start": row.training_window_start.isoformat() if row.training_window_start else None,
            "training_window_end": row.training_window_end.isoformat() if row.training_window_end else None,
            "validation_window_start": row.validation_window_start.isoformat() if row.validation_window_start else None,
            "validation_window_end": row.validation_window_end.isoformat() if row.validation_window_end else None,
            "metrics": dict(row.metrics or {}),
            "params": dict(row.params or {}),
            "notes": row.notes,
            "recommendation": asdict(recommendation),
        }

    def write(self, *, model_version: str, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build(model_version=model_version), indent=2), encoding="utf-8")
        return path

    def compare_models(self, *, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.registry.recent(limit=limit)
        output: list[dict[str, Any]] = []
        for row in rows:
            recommendation = recommend_from_run(row)
            metrics = dict(row.metrics or {})
            output.append(
                {
                    "model_version": row.model_version,
                    "status": row.status,
                    "promoted": row.promoted,
                    "feature_set_version": row.feature_set_version,
                    "training_window_start": row.training_window_start.isoformat() if row.training_window_start else None,
                    "training_window_end": row.training_window_end.isoformat() if row.training_window_end else None,
                    "validation_window_start": row.validation_window_start.isoformat() if row.validation_window_start else None,
                    "validation_window_end": row.validation_window_end.isoformat() if row.validation_window_end else None,
                    "validation_row_count": metrics.get("validation_row_count"),
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "brier_score": metrics.get("brier_score"),
                    "roc_auc": metrics.get("roc_auc"),
                    "recommendation": recommendation.recommendation,
                }
            )
        return output

    def latest_status(self) -> dict[str, Any]:
        row = self.registry.latest_promoted() or self.registry.latest()
        if row is None:
            return {"status": "UNAVAILABLE"}
        recommendation = recommend_from_run(row)
        metrics = dict(row.metrics or {})
        return {
            "status": row.status,
            "model_version": row.model_version,
            "feature_set_version": row.feature_set_version,
            "promoted": row.promoted,
            "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
            "training_window_start": row.training_window_start.isoformat() if row.training_window_start else None,
            "training_window_end": row.training_window_end.isoformat() if row.training_window_end else None,
            "validation_window_start": row.validation_window_start.isoformat() if row.validation_window_start else None,
            "validation_window_end": row.validation_window_end.isoformat() if row.validation_window_end else None,
            "validation_row_count": metrics.get("validation_row_count"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "brier_score": metrics.get("brier_score"),
            "roc_auc": metrics.get("roc_auc"),
            "recommendation": recommendation.recommendation,
            "recommendation_reasons": recommendation.reasons,
        }

    def _require_row(self, model_version: str) -> ModelRun:
        row = self.registry.get(model_version)
        if row is None:
            raise ValueError(f"Unknown model version: {model_version}")
        return row


def recommend_from_run(row: ModelRun) -> PromotionRecommendation:
    metrics = dict(row.metrics or {})
    reasons: list[str] = []
    validation_row_count = int(metrics.get("validation_row_count") or 0)

    if row.status not in {MODEL_STATUS_VALIDATED, "PROMOTED"}:
        reasons.append("MODEL_NOT_VALIDATED")
    if validation_row_count <= 0:
        reasons.append("VALIDATION_ROWS_MISSING")
    if metrics.get("base_rate") is None:
        reasons.append("BASE_RATE_MISSING")
    if metrics.get("score_band_expectancy") in (None, []):
        reasons.append("SCORE_BAND_SUMMARY_MISSING")
    if metrics.get("brier_score") is None:
        reasons.append("BRIER_SCORE_MISSING")
    if int(metrics.get("train_positive_count") or 0) <= 0:
        reasons.append("TRAINING_POSITIVE_CLASS_MISSING")
    if int(metrics.get("train_negative_count") or 0) <= 0:
        reasons.append("TRAINING_NEGATIVE_CLASS_MISSING")
    if metrics.get("roc_auc") is None and validation_row_count > 0:
        reasons.append("VALIDATION_SINGLE_CLASS")

    recommendation = "RECOMMEND_PROMOTE" if not reasons else "RECOMMEND_REJECT"
    return PromotionRecommendation(
        model_version=row.model_version,
        recommendation=recommendation,
        reasons=reasons,
        validation_row_count=validation_row_count,
    )


__all__ = [
    "BaselineRetrainer",
    "PromotionRecommendation",
    "ValidationReporter",
    "recommend_from_run",
]
