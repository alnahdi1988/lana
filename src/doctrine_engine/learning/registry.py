from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.db.models.learning import ModelRun
from doctrine_engine.learning.schemas import BASELINE_MODEL_NAME


class ModelRunRegistry:
    def __init__(self, *, session_factory: sessionmaker[Session], model_name: str = BASELINE_MODEL_NAME) -> None:
        self.session_factory = session_factory
        self.model_name = model_name

    def upsert(
        self,
        *,
        model_version: str,
        feature_set_version: str,
        status: str,
        training_window_start: datetime | None,
        training_window_end: datetime | None,
        validation_window_start: datetime | None,
        validation_window_end: datetime | None,
        artifact_uri: str | None,
        metrics: dict[str, Any],
        params: dict[str, Any],
        notes: str | None = None,
        promoted: bool = False,
        promoted_at: datetime | None = None,
    ) -> ModelRun:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            row = session.scalar(
                select(ModelRun).where(
                    ModelRun.model_name == self.model_name,
                    ModelRun.model_version == model_version,
                )
            )
            if row is None:
                row = ModelRun(
                    model_name=self.model_name,
                    model_version=model_version,
                    feature_set_version=feature_set_version,
                    status=status,
                    training_window_start=training_window_start,
                    training_window_end=training_window_end,
                    validation_window_start=validation_window_start,
                    validation_window_end=validation_window_end,
                    artifact_uri=artifact_uri,
                    metrics=dict(metrics),
                    params=dict(params),
                    notes=notes,
                    promoted=promoted,
                    promoted_at=promoted_at or (datetime.now(timezone.utc) if promoted else None),
                )
                session.add(row)
            else:
                row.feature_set_version = feature_set_version or row.feature_set_version
                row.status = status
                row.training_window_start = training_window_start or row.training_window_start
                row.training_window_end = training_window_end or row.training_window_end
                row.validation_window_start = validation_window_start or row.validation_window_start
                row.validation_window_end = validation_window_end or row.validation_window_end
                row.artifact_uri = artifact_uri or row.artifact_uri
                row.metrics = {**(row.metrics or {}), **dict(metrics)}
                row.params = {**(row.params or {}), **dict(params)}
                row.notes = notes or row.notes
                row.promoted = promoted or row.promoted
                if promoted:
                    row.promoted_at = promoted_at or row.promoted_at or datetime.now(timezone.utc)
            session.commit()
            session.refresh(row)
            return row

    def get(self, model_version: str) -> ModelRun | None:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            return session.scalar(
                select(ModelRun)
                .where(
                    ModelRun.model_name == self.model_name,
                    ModelRun.model_version == model_version,
                )
            )

    def latest(self) -> ModelRun | None:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            return session.scalar(
                select(ModelRun)
                .where(ModelRun.model_name == self.model_name)
                .order_by(desc(ModelRun.updated_at), desc(ModelRun.created_at))
                .limit(1)
            )

    def latest_promoted(self) -> ModelRun | None:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            return session.scalar(
                select(ModelRun)
                .where(ModelRun.model_name == self.model_name, ModelRun.promoted.is_(True))
                .order_by(desc(ModelRun.promoted_at), desc(ModelRun.updated_at), desc(ModelRun.created_at))
                .limit(1)
            )

    def find_by_training_window(self, *, training_window_start: datetime, training_window_end: datetime) -> ModelRun | None:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            return session.scalar(
                select(ModelRun)
                .where(
                    ModelRun.model_name == self.model_name,
                    ModelRun.training_window_start == training_window_start,
                    ModelRun.training_window_end == training_window_end,
                )
                .order_by(desc(ModelRun.updated_at), desc(ModelRun.created_at))
                .limit(1)
            )

    def recent(self, *, limit: int = 10) -> list[ModelRun]:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            return list(
                session.scalars(
                    select(ModelRun)
                    .where(ModelRun.model_name == self.model_name)
                    .order_by(desc(ModelRun.updated_at), desc(ModelRun.created_at))
                    .limit(limit)
                )
            )

    def promote(self, model_version: str) -> ModelRun:
        with self.session_factory() as session:
            self._normalize_duplicates(session)
            target = session.scalar(
                select(ModelRun)
                .where(
                    ModelRun.model_name == self.model_name,
                    ModelRun.model_version == model_version,
                )
            )
            if target is None:
                raise ValueError(f"Unknown model version: {model_version}")
            if target.status not in {"VALIDATED", "PROMOTED"}:
                raise ValueError(f"Model version {model_version} must be VALIDATED before promotion.")
            now = datetime.now(timezone.utc)
            for row in session.scalars(
                select(ModelRun).where(ModelRun.model_name == self.model_name, ModelRun.promoted.is_(True))
            ):
                if row.model_version == model_version:
                    continue
                row.promoted = False
                if row.status == "PROMOTED":
                    row.status = "VALIDATED"
            target.promoted = True
            target.promoted_at = now
            target.status = "PROMOTED"
            session.commit()
            session.refresh(target)
            return target

    def _normalize_duplicates(self, session: Session) -> None:
        rows = list(
            session.scalars(
                select(ModelRun)
                .where(ModelRun.model_name == self.model_name)
                .order_by(
                    desc(ModelRun.promoted_at),
                    desc(ModelRun.updated_at),
                    desc(ModelRun.created_at),
                )
            )
        )
        grouped: dict[str, list[ModelRun]] = {}
        for row in rows:
            grouped.setdefault(row.model_version, []).append(row)

        changed = False
        for duplicates in grouped.values():
            keeper = duplicates[0]
            for duplicate in duplicates[1:]:
                keeper.feature_set_version = keeper.feature_set_version or duplicate.feature_set_version
                keeper.training_window_start = keeper.training_window_start or duplicate.training_window_start
                keeper.training_window_end = keeper.training_window_end or duplicate.training_window_end
                keeper.validation_window_start = keeper.validation_window_start or duplicate.validation_window_start
                keeper.validation_window_end = keeper.validation_window_end or duplicate.validation_window_end
                keeper.artifact_uri = keeper.artifact_uri or duplicate.artifact_uri
                keeper.metrics = {**(duplicate.metrics or {}), **(keeper.metrics or {})}
                keeper.params = {**(duplicate.params or {}), **(keeper.params or {})}
                keeper.notes = _merge_notes(keeper.notes, duplicate.notes)
                if duplicate.promoted and not keeper.promoted:
                    keeper.promoted = True
                    keeper.promoted_at = duplicate.promoted_at or keeper.promoted_at or datetime.now(timezone.utc)
                if keeper.status == "TRAINED" and duplicate.status in {"VALIDATED", "PROMOTED"}:
                    keeper.status = duplicate.status
                session.delete(duplicate)
                changed = True
            if keeper.promoted:
                if keeper.status != "PROMOTED":
                    keeper.status = "PROMOTED"
                    changed = True
        if changed:
            session.commit()


__all__ = ["ModelRunRegistry"]


def _merge_notes(left: str | None, right: str | None) -> str | None:
    parts = [part for part in (left, right) if part]
    if not parts:
        return None
    deduped: list[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    return "\n".join(deduped)
