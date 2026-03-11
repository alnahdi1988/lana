from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from doctrine_engine.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from doctrine_engine.db.types import MarketDataSource, Timeframe

TIMEFRAME_ENUM = Enum(
    Timeframe,
    name="timeframe",
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class Bar(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint(
            "symbol_id",
            "timeframe",
            "bar_timestamp",
            "adjustment",
            name="uq_bars_symbol_timeframe_bar_timestamp_adjustment",
        ),
        CheckConstraint("high_price >= low_price", name="bars_high_ge_low"),
        CheckConstraint("volume >= 0", name="bars_volume_non_negative"),
        Index("ix_bars_symbol_timeframe_known_at", "symbol_id", "timeframe", "known_at"),
        Index("ix_bars_timeframe_bar_timestamp", "timeframe", "bar_timestamp"),
    )

    symbol_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    timeframe: Mapped[Timeframe] = mapped_column(
        TIMEFRAME_ENUM,
        nullable=False,
    )
    bar_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    trade_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[MarketDataSource] = mapped_column(
        Enum(MarketDataSource, name="market_data_source"),
        nullable=False,
        default=MarketDataSource.POLYGON,
    )
    adjustment: Mapped[str] = mapped_column(String(32), nullable=False, default="SPLIT_ADJUSTED")
