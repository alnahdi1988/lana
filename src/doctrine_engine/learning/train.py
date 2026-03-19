from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.features import feature_column_names, to_feature_matrix
from doctrine_engine.learning.registry import ModelRunRegistry
from doctrine_engine.learning.schemas import (
    BASELINE_MODEL_NAME,
    BOOLEAN_FEATURE_NAMES,
    CATEGORICAL_FEATURE_NAMES,
    FEATURE_SET_VERSION,
    MODEL_STATUS_FAILED,
    MODEL_STATUS_TRAINED,
    ModelArtifactRecord,
    NUMERIC_FEATURE_NAMES,
)


MIN_FINALIZED_ROWS = 10


class BaselineTrainer:
    def __init__(self, *, dataset: LifecycleLearningDataset, registry: ModelRunRegistry) -> None:
        self.dataset = dataset
        self.registry = registry

    def train(
        self,
        *,
        train_start: datetime,
        train_end: datetime,
        artifact_dir: str | Path,
    ) -> ModelArtifactRecord:
        examples = self.dataset.examples(finalized_only=True, known_at_start=train_start, known_at_end=train_end)
        labeled = [item for item in examples if item.success_label is not None]
        self._validate_training_rows(labeled)

        X = to_feature_matrix(labeled)
        y = [1 if item.success_label else 0 for item in labeled]
        pipeline = build_pipeline()
        pipeline.fit(X, y)

        model_version = build_model_version(train_start=train_start, train_end=train_end, row_count=len(labeled))
        output_dir = Path(artifact_dir) / model_version
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "model.joblib"
        metadata_path = output_dir / "metadata.json"
        metadata = ModelArtifactRecord(
            model_name=BASELINE_MODEL_NAME,
            model_version=model_version,
            feature_set_version=FEATURE_SET_VERSION,
            artifact_uri=str(artifact_path.resolve()),
            training_window_start=train_start,
            training_window_end=train_end,
            validation_window_start=None,
            validation_window_end=None,
            row_count=len(labeled),
            params={
                "model": "LogisticRegression",
                "random_state": 0,
                "max_iter": 1000,
                "min_finalized_rows": MIN_FINALIZED_ROWS,
            },
            metrics={
                "train_row_count": len(labeled),
                "train_positive_count": sum(y),
                "train_negative_count": len(y) - sum(y),
                "positive_rate": sum(y) / len(y),
            },
        )
        joblib.dump(
            {
                "pipeline": pipeline,
                "feature_columns": feature_column_names(),
                "model_name": BASELINE_MODEL_NAME,
                "model_version": model_version,
                "feature_set_version": FEATURE_SET_VERSION,
            },
            artifact_path,
        )
        metadata_path.write_text(json.dumps(record_to_json(metadata), indent=2), encoding="utf-8")
        self.registry.upsert(
            model_version=model_version,
            feature_set_version=FEATURE_SET_VERSION,
            status=MODEL_STATUS_TRAINED,
            training_window_start=train_start,
            training_window_end=train_end,
            validation_window_start=None,
            validation_window_end=None,
            artifact_uri=str(artifact_path.resolve()),
            metrics=metadata.metrics,
            params=metadata.params,
        )
        return metadata

    def record_failure(
        self,
        *,
        train_start: datetime,
        train_end: datetime,
        message: str,
        artifact_dir: str | Path,
    ) -> None:
        model_version = build_model_version(train_start=train_start, train_end=train_end, row_count=0)
        self.registry.upsert(
            model_version=model_version,
            feature_set_version=FEATURE_SET_VERSION,
            status=MODEL_STATUS_FAILED,
            training_window_start=train_start,
            training_window_end=train_end,
            validation_window_start=None,
            validation_window_end=None,
            artifact_uri=str((Path(artifact_dir) / model_version).resolve()),
            metrics={},
            params={"model": "LogisticRegression", "failure_reason": message},
            notes=message,
        )

    @staticmethod
    def _validate_training_rows(rows) -> None:
        if len(rows) < MIN_FINALIZED_ROWS:
            raise ValueError(
                f"Baseline training requires at least {MIN_FINALIZED_ROWS} finalized labeled rows; found {len(rows)}."
            )
        classes = {item.success_label for item in rows}
        if classes != {False, True}:
            raise ValueError("Baseline training requires both winning and losing finalized rows.")


def build_pipeline() -> Pipeline:
    ordered_names = feature_column_names()
    numeric_indices = [ordered_names.index(name) for name in NUMERIC_FEATURE_NAMES + BOOLEAN_FEATURE_NAMES]
    categorical_indices = [ordered_names.index(name) for name in CATEGORICAL_FEATURE_NAMES]
    return Pipeline(
        steps=[
            (
                "preprocess",
                ColumnTransformer(
                    transformers=[
                        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_indices),
                        ("numeric", "passthrough", numeric_indices),
                    ]
                ),
            ),
            ("model", LogisticRegression(max_iter=1000, random_state=0)),
        ]
    )


def build_model_version(*, train_start: datetime, train_end: datetime, row_count: int) -> str:
    payload = f"{train_start.isoformat()}|{train_end.isoformat()}|{row_count}|{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def record_to_json(record: ModelArtifactRecord) -> dict[str, Any]:
    payload = asdict(record)
    for key in ("training_window_start", "training_window_end", "validation_window_start", "validation_window_end"):
        if payload[key] is not None:
            payload[key] = payload[key].isoformat()
    return payload


__all__ = ["BaselineTrainer", "MIN_FINALIZED_ROWS", "build_pipeline", "record_to_json"]
