from __future__ import annotations

from pathlib import Path

import joblib

from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.features import to_feature_matrix
from doctrine_engine.learning.registry import ModelRunRegistry


class BaselineScorer:
    def __init__(self, *, dataset: LifecycleLearningDataset, registry: ModelRunRegistry) -> None:
        self.dataset = dataset
        self.registry = registry

    def score_latest(self, *, limit: int, model_version: str | None = None) -> list[dict]:
        run = self._resolve_run(model_version=model_version)
        artifact = joblib.load(Path(run.artifact_uri))
        examples = self.dataset.examples(limit=limit)
        if not examples:
            return []
        probabilities = artifact["pipeline"].predict_proba(to_feature_matrix(examples))[:, 1]
        rows: list[dict] = []
        for example, probability in zip(examples, probabilities, strict=True):
            rows.append(
                {
                    "signal_id": example.signal_id,
                    "ticker": example.ticker,
                    "known_at": example.known_at.isoformat(),
                    "setup_state": example.features["setup_state"],
                    "grade": example.features["grade"],
                    "baseline_score": round(float(probability), 6),
                    "model_version": run.model_version,
                }
            )
        rows.sort(key=lambda item: item["baseline_score"], reverse=True)
        return rows

    def _resolve_run(self, *, model_version: str | None):
        if model_version:
            run = self.registry.get(model_version)
        else:
            run = self.registry.latest_promoted() or self.registry.latest()
        if run is None or not run.artifact_uri:
            raise ValueError("No trained baseline model is available to score rows.")
        return run


__all__ = ["BaselineScorer"]
