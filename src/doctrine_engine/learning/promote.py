from __future__ import annotations

from doctrine_engine.learning.registry import ModelRunRegistry


class ModelPromoter:
    def __init__(self, *, registry: ModelRunRegistry) -> None:
        self.registry = registry

    def promote(self, *, model_version: str):
        return self.registry.promote(model_version)

    def status(self, *, limit: int = 10) -> list[dict]:
        return [
            {
                "model_version": row.model_version,
                "status": row.status,
                "promoted": row.promoted,
                "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
                "training_window_start": row.training_window_start.isoformat() if row.training_window_start else None,
                "training_window_end": row.training_window_end.isoformat() if row.training_window_end else None,
                "validation_window_start": row.validation_window_start.isoformat() if row.validation_window_start else None,
                "validation_window_end": row.validation_window_end.isoformat() if row.validation_window_end else None,
                "artifact_uri": row.artifact_uri,
            }
            for row in self.registry.recent(limit=limit)
        ]


__all__ = ["ModelPromoter"]
