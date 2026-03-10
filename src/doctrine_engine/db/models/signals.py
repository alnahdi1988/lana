from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from doctrine_engine.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from doctrine_engine.db.types import EntryType, EvaluationStatus, HTFBias, SignalGrade, SignalValue, TrailMode


class Signal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="signals_confidence_between_zero_and_one"),
        Index("ix_signals_symbol_signal_timestamp", "symbol_id", "signal_timestamp"),
        Index("ix_signals_known_at", "known_at"),
        Index("ix_signals_signal", "signal"),
        Index("ix_signals_grade", "grade"),
        Index("ix_signals_bias_htf", "bias_htf"),
        Index("ix_signals_setup_state", "setup_state"),
    )

    symbol_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    universe_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("universe_snapshots.id", ondelete="SET NULL"),
    )
    signal_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    htf_bar_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mtf_bar_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ltf_bar_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signal: Mapped[SignalValue] = mapped_column(
        Enum(SignalValue, name="signal_value"),
        nullable=False,
    )
    signal_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    grade: Mapped[SignalGrade] = mapped_column(
        Enum(SignalGrade, name="signal_grade"),
        nullable=False,
    )
    bias_htf: Mapped[HTFBias] = mapped_column(
        Enum(HTFBias, name="htf_bias"),
        nullable=False,
    )
    setup_state: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
    )
    event_risk_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extensible_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    trade_plan: Mapped["TradePlan | None"] = relationship(back_populates="signal", uselist=False)
    outcome: Mapped["Outcome | None"] = relationship(back_populates="signal", uselist=False)


class TradePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trade_plans"
    __table_args__ = (
        UniqueConstraint("signal_id", name="uq_trade_plans_signal_id"),
        CheckConstraint("entry_zone_low <= entry_zone_high", name="trade_plans_entry_zone_low_le_high"),
        Index("ix_trade_plans_signal_id", "signal_id"),
        Index("ix_trade_plans_plan_timestamp", "plan_timestamp"),
        Index("ix_trade_plans_known_at", "known_at"),
    )

    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type"),
        nullable=False,
        default=EntryType.BASE,
    )
    entry_zone_low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    entry_zone_high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    confirmation_level: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    invalidation_level: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    tp1: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    tp2: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    trail_mode: Mapped[TrailMode] = mapped_column(
        Enum(TrailMode, name="trail_mode"),
        nullable=False,
        default=TrailMode.STRUCTURAL,
    )
    plan_reason_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
    )
    extensible_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    signal: Mapped["Signal"] = relationship(back_populates="trade_plan")


class Outcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("signal_id", name="uq_outcomes_signal_id"),
        Index("ix_outcomes_signal_id", "signal_id"),
        Index("ix_outcomes_evaluation_status", "evaluation_status"),
        Index("ix_outcomes_tracked_until", "tracked_until"),
    )

    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation_status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status"),
        nullable=False,
        default=EvaluationStatus.PENDING,
    )
    evaluation_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bars_tracked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_barrier: Mapped[str | None] = mapped_column(String(32))
    success_label: Mapped[bool | None] = mapped_column(Boolean)
    tp2_label: Mapped[bool | None] = mapped_column(Boolean)
    invalidated_first: Mapped[bool | None] = mapped_column(Boolean)
    mfe_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    mae_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    bars_to_tp1: Mapped[int | None] = mapped_column(Integer)
    extensible_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    signal: Mapped["Signal"] = relationship(back_populates="outcome")
