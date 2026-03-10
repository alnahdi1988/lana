from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from doctrine_engine.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ModelRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_runs"

    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_set_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    training_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(128), index=True)
    artifact_uri: Mapped[str | None] = mapped_column(String(512))
    promoted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(String(2048))
