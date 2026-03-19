from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score

from doctrine_engine.learning.artifact import load_compatible_artifact
from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.features import to_feature_matrix
from doctrine_engine.learning.registry import ModelRunRegistry
from doctrine_engine.learning.schemas import FEATURE_SET_VERSION, MODEL_STATUS_VALIDATED, ModelArtifactRecord
from doctrine_engine.learning.train import BaselineTrainer, record_to_json


class BaselineValidator:
    def __init__(self, *, dataset: LifecycleLearningDataset, registry: ModelRunRegistry) -> None:
        self.dataset = dataset
        self.registry = registry

    def validate(
        self,
        *,
        train_start: datetime,
        train_end: datetime,
        validate_start: datetime,
        validate_end: datetime,
        artifact_dir: str | Path,
        reuse_existing_training: bool = True,
    ) -> ModelArtifactRecord:
        _validate_windows(
            train_start=train_start,
            train_end=train_end,
            validate_start=validate_start,
            validate_end=validate_end,
        )
        trained = self._resolve_trained_model(
            train_start=train_start,
            train_end=train_end,
            artifact_dir=artifact_dir,
            reuse_existing_training=reuse_existing_training,
        )
        artifact = load_compatible_artifact(trained.artifact_uri)
        validation_rows = [
            item
            for item in self.dataset.examples(
                finalized_only=True,
                known_at_start=validate_start,
                known_at_end=validate_end,
            )
            if item.success_label is not None
        ]
        if not validation_rows:
            raise ValueError("Walk-forward validation requires at least one finalized labeled validation row.")

        y_true = [1 if item.success_label else 0 for item in validation_rows]
        probabilities = artifact["pipeline"].predict_proba(to_feature_matrix(validation_rows))[:, 1]
        y_pred = [1 if value >= 0.5 else 0 for value in probabilities]
        metrics = {
            "validation_row_count": len(validation_rows),
            "base_rate": sum(y_true) / len(y_true),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "brier_score": float(brier_score_loss(y_true, probabilities)),
            "roc_auc": _safe_auc(y_true, probabilities),
            "calibration_buckets": _calibration_buckets(probabilities, y_true),
            "score_band_expectancy": _score_band_expectancy(validation_rows, probabilities),
        }

        metadata = ModelArtifactRecord(
            model_name=trained.model_name,
            model_version=trained.model_version,
            feature_set_version=trained.feature_set_version,
            artifact_uri=trained.artifact_uri,
            training_window_start=train_start,
            training_window_end=train_end,
            validation_window_start=validate_start,
            validation_window_end=validate_end,
            row_count=trained.row_count,
            params=trained.params,
            metrics={**trained.metrics, **metrics},
        )
        metadata_path = Path(trained.artifact_uri).with_name("validation.json")
        metadata_path.write_text(json.dumps(record_to_json(metadata), indent=2), encoding="utf-8")
        self.registry.upsert(
            model_version=trained.model_version,
            feature_set_version=FEATURE_SET_VERSION,
            status=MODEL_STATUS_VALIDATED,
            training_window_start=train_start,
            training_window_end=train_end,
            validation_window_start=validate_start,
            validation_window_end=validate_end,
            artifact_uri=trained.artifact_uri,
            metrics=metadata.metrics,
            params=trained.params,
        )
        return metadata

    def _resolve_trained_model(
        self,
        *,
        train_start: datetime,
        train_end: datetime,
        artifact_dir: str | Path,
        reuse_existing_training: bool,
    ) -> ModelArtifactRecord:
        if reuse_existing_training:
            existing = self.registry.find_by_training_window(
                training_window_start=train_start,
                training_window_end=train_end,
            )
            if existing is not None and existing.artifact_uri:
                return ModelArtifactRecord(
                    model_name=existing.model_name,
                    model_version=existing.model_version,
                    feature_set_version=existing.feature_set_version or FEATURE_SET_VERSION,
                    artifact_uri=existing.artifact_uri,
                    training_window_start=existing.training_window_start or train_start,
                    training_window_end=existing.training_window_end or train_end,
                    validation_window_start=existing.validation_window_start,
                    validation_window_end=existing.validation_window_end,
                    row_count=int((existing.metrics or {}).get("train_row_count") or 0),
                    params=dict(existing.params or {}),
                    metrics=dict(existing.metrics or {}),
                )
        trainer = BaselineTrainer(dataset=self.dataset, registry=self.registry)
        return trainer.train(train_start=train_start, train_end=train_end, artifact_dir=artifact_dir)


def _safe_auc(y_true: list[int], probabilities) -> float | None:
    if len(set(y_true)) < 2:
        return None
    return float(roc_auc_score(y_true, probabilities))


def _calibration_buckets(probabilities, y_true: list[int]) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    ranges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    for start, end in ranges:
        bucket_values = [value for value in zip(probabilities, y_true, strict=True) if start <= value[0] < end]
        if not bucket_values:
            continue
        predicted = sum(value[0] for value in bucket_values) / len(bucket_values)
        actual = sum(value[1] for value in bucket_values) / len(bucket_values)
        buckets.append(
            {
                "band": f"{start:.1f}-{min(end, 1.0):.1f}",
                "count": len(bucket_values),
                "avg_predicted": round(float(predicted), 6),
                "avg_actual": round(float(actual), 6),
            }
        )
    return buckets


def _score_band_expectancy(rows, probabilities) -> list[dict[str, Any]]:
    bands = [(0.0, 0.33), (0.33, 0.66), (0.66, 1.01)]
    output: list[dict[str, Any]] = []
    for start, end in bands:
        bucket = [(row, prob) for row, prob in zip(rows, probabilities, strict=True) if start <= prob < end]
        if not bucket:
            continue
        output.append(
            {
                "band": f"{start:.2f}-{min(end, 1.0):.2f}",
                "count": len(bucket),
                "success_rate": round(sum(1 if row.success_label else 0 for row, _ in bucket) / len(bucket), 6),
                "tp2_rate": round(sum(1 if row.tp2_label else 0 for row, _ in bucket) / len(bucket), 6),
                "avg_mfe_pct": round(sum((row.mfe_pct or 0.0) for row, _ in bucket) / len(bucket), 6),
                "avg_mae_pct": round(sum((row.mae_pct or 0.0) for row, _ in bucket) / len(bucket), 6),
            }
        )
    return output


__all__ = ["BaselineValidator"]


def _validate_windows(
    *,
    train_start: datetime,
    train_end: datetime,
    validate_start: datetime,
    validate_end: datetime,
) -> None:
    if train_end <= train_start:
        raise ValueError("Training window must satisfy train_end > train_start.")
    if validate_end <= validate_start:
        raise ValueError("Validation window must satisfy validate_end > validate_start.")
    if validate_start <= train_end:
        raise ValueError("Walk-forward validation requires validate_start > train_end with no overlap.")
