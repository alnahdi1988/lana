from __future__ import annotations

from pathlib import Path

from doctrine_engine.learning.artifact import load_compatible_artifact
from doctrine_engine.learning.dataset import LifecycleLearningDataset
from doctrine_engine.learning.features import to_feature_matrix
from doctrine_engine.learning.registry import ModelRunRegistry


class BaselineScorer:
    def __init__(self, *, dataset: LifecycleLearningDataset, registry: ModelRunRegistry) -> None:
        self.dataset = dataset
        self.registry = registry

    def score_latest(self, *, limit: int, model_version: str | None = None) -> list[dict]:
        run, artifact = self._resolve_scoring_target(model_version=model_version)
        examples = self.dataset.examples(limit=limit, newest_first=True)
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

    def _resolve_scoring_target(self, *, model_version: str | None):
        if model_version:
            run = self.registry.get(model_version)
            if run is None or not run.artifact_uri:
                raise ValueError("No trained baseline model is available to score rows.")
            return run, load_compatible_artifact(Path(run.artifact_uri))

        seen_versions: set[str] = set()
        candidates = []
        promoted = self.registry.latest_promoted()
        if promoted is not None:
            candidates.append(promoted)
            seen_versions.add(promoted.model_version)
        recent_runs = self.registry.recent(limit=20)
        for allowed_statuses in ({"PROMOTED", "VALIDATED"}, {"TRAINED"}):
            for row in recent_runs:
                if row.model_version in seen_versions or row.status not in allowed_statuses:
                    continue
                candidates.append(row)
                seen_versions.add(row.model_version)

        errors: list[str] = []
        for run in candidates:
            if not run.artifact_uri:
                continue
            try:
                artifact = load_compatible_artifact(Path(run.artifact_uri))
            except ValueError as exc:
                errors.append(f"{run.model_version}: {exc}")
                continue
            return run, artifact

        if errors:
            raise ValueError(
                "No compatible trained baseline model is available to score rows. "
                + "Tried: "
                + " | ".join(errors)
            )
        raise ValueError("No trained baseline model is available to score rows.")
__all__ = ["BaselineScorer"]
