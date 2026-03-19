from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

from doctrine_engine.learning.features import build_learning_example
from doctrine_engine.learning.schemas import FEATURE_SET_VERSION, LearningDatasetSummary, LearningExample
from doctrine_engine.product.ml_dataset import LifecycleDatasetExporter


class LifecycleLearningDataset:
    def __init__(self, *, exporter: LifecycleDatasetExporter) -> None:
        self.exporter = exporter

    def examples(
        self,
        *,
        limit: int | None = None,
        finalized_only: bool = False,
        known_at_start: datetime | None = None,
        known_at_end: datetime | None = None,
    ) -> list[LearningExample]:
        rows = self.exporter.export_rows(limit=limit)
        examples = [build_learning_example(row) for row in rows]
        return [
            example
            for example in examples
            if (not finalized_only or example.evaluation_status == "FINALIZED")
            and (known_at_start is None or example.known_at >= known_at_start)
            and (known_at_end is None or example.known_at <= known_at_end)
        ]

    def export_json(
        self,
        output_path: str | Path,
        *,
        limit: int | None = None,
        finalized_only: bool = False,
    ) -> LearningDatasetSummary:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [self._serialize(example) for example in self.examples(limit=limit, finalized_only=finalized_only)]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.summary(limit=limit, finalized_only=finalized_only)

    def summary(self, *, limit: int | None = None, finalized_only: bool = False) -> LearningDatasetSummary:
        examples = self.examples(limit=limit, finalized_only=finalized_only)
        labeled = [item for item in examples if item.success_label is not None]
        positive = sum(1 for item in labeled if item.success_label is True)
        negative = sum(1 for item in labeled if item.success_label is False)
        pending = sum(1 for item in examples if item.evaluation_status == "PENDING")
        finalized = sum(1 for item in examples if item.evaluation_status == "FINALIZED")
        return LearningDatasetSummary(
            dataset_version=FEATURE_SET_VERSION,
            total_rows=len(examples),
            pending_rows=pending,
            finalized_rows=finalized,
            labeled_rows=len(labeled),
            positive_rows=positive,
            negative_rows=negative,
        )

    @staticmethod
    def _serialize(example: LearningExample) -> dict:
        return {
            "signal_id": example.signal_id,
            "ticker": example.ticker,
            "signal_timestamp": example.signal_timestamp.isoformat(),
            "known_at": example.known_at.isoformat(),
            "evaluation_status": example.evaluation_status,
            "success_label": example.success_label,
            "tp2_label": example.tp2_label,
            "invalidated_first": example.invalidated_first,
            "mfe_pct": example.mfe_pct,
            "mae_pct": example.mae_pct,
            "features": dict(example.features),
        }


__all__ = ["LifecycleLearningDataset"]
