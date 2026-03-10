from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from doctrine_engine.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from doctrine_engine.db.types import (
    ListedExchange,
    MarketDataSource,
    UniverseRefreshSession,
    UniverseTier,
)


class Symbol(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "symbols"

    ticker: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    polygon_ticker: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    exchange: Mapped[ListedExchange] = mapped_column(
        Enum(ListedExchange, name="listed_exchange"),
        nullable=False,
    )
    security_type: Mapped[str] = mapped_column(String(32), nullable=False, default="COMMON_STOCK")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_etf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_otc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_reference_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    last_reference_price_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cik: Mapped[str | None] = mapped_column(String(20))
    primary_listing: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    universe_memberships: Mapped[list["UniverseMembership"]] = relationship(
        back_populates="symbol",
        cascade="all, delete-orphan",
    )


class UniverseSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "universe_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_timestamp",
            "refresh_session",
            name="uq_universe_snapshots_snapshot_timestamp_session",
        ),
    )

    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    refresh_session: Mapped[UniverseRefreshSession] = mapped_column(
        Enum(UniverseRefreshSession, name="universe_refresh_session"),
        nullable=False,
    )
    source: Mapped[MarketDataSource] = mapped_column(
        Enum(MarketDataSource, name="market_data_source"),
        nullable=False,
        default=MarketDataSource.POLYGON,
    )
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    memberships: Mapped[list["UniverseMembership"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class UniverseMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "universe_snapshot_memberships"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "symbol_id",
            name="uq_universe_snapshot_memberships_snapshot_symbol",
        ),
        Index("ix_universe_snapshot_memberships_snapshot_id", "snapshot_id"),
        Index("ix_universe_snapshot_memberships_symbol_id", "symbol_id"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("universe_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol_ticker_cache: Mapped[str | None] = mapped_column(String(16))
    hard_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tier: Mapped[UniverseTier | None] = mapped_column(Enum(UniverseTier, name="universe_tier"))
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    avg_daily_volume_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    avg_dollar_volume_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    sufficient_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_quality_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
    )
    quality_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    snapshot: Mapped["UniverseSnapshot"] = relationship(back_populates="memberships")
    symbol: Mapped["Symbol"] = relationship(back_populates="universe_memberships")
