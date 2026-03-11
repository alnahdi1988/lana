from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from doctrine_engine.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from doctrine_engine.db.types import Timeframe

TIMEFRAME_ENUM = Enum(
    Timeframe,
    name="timeframe",
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class Feature(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint(
            "symbol_id",
            "timeframe",
            "feature_set",
            "feature_version",
            "bar_timestamp",
            name="uq_features_symbol_timeframe_set_version_bar_timestamp",
        ),
        Index("ix_features_symbol_id", "symbol_id"),
        Index("ix_features_bar_timestamp", "bar_timestamp"),
        Index("ix_features_known_at", "known_at"),
    )

    symbol_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    timeframe: Mapped[Timeframe | None] = mapped_column(TIMEFRAME_ENUM)
    feature_set: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    bar_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
