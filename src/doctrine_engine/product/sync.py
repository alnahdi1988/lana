from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.db.models.market_data import Bar
from doctrine_engine.db.models.symbols import Symbol, UniverseMembership, UniverseSnapshot
from doctrine_engine.db.types import ListedExchange, MarketDataSource, Timeframe, UniverseRefreshSession, UniverseTier
from doctrine_engine.engines.models import EngineBar
from doctrine_engine.engines.pattern_engine import PatternEngine
from doctrine_engine.engines.persistence import upsert_feature_result
from doctrine_engine.engines.structure_engine import StructureEngine
from doctrine_engine.engines.zone_engine import ZoneEngine
from doctrine_engine.product.adapters import ALERT_BENCHMARKS, SECTOR_ETF_MAP
from doctrine_engine.product.clients import PolygonClient
from doctrine_engine.runner.models import RunnerConfig


@dataclass(frozen=True, slots=True)
class SyncResult:
    snapshot_id: uuid.UUID
    synced_tickers: list[str]
    errors: list[str]


class PolygonSyncService:
    TIMEFRAME_SPECS = {
        Timeframe.MIN_5: (5, "minute"),
        Timeframe.MIN_15: (15, "minute"),
        Timeframe.HOUR_1: (1, "hour"),
        Timeframe.HOUR_4: (4, "hour"),
        Timeframe.DAY_1: (1, "day"),
    }

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        polygon_client: PolygonClient,
        universe_refresh_limit: int,
        min_price: Decimal,
        max_price: Decimal,
        min_avg_volume_20d: Decimal,
        min_avg_dollar_volume_20d: Decimal,
        intraday_lookback_days: int,
        daily_lookback_days: int,
        history_window_bars: int,
        structure_engine: StructureEngine | None = None,
        zone_engine: ZoneEngine | None = None,
        pattern_engine: PatternEngine | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.polygon_client = polygon_client
        self.universe_refresh_limit = universe_refresh_limit
        self.min_price = min_price
        self.max_price = max_price
        self.min_avg_volume_20d = min_avg_volume_20d
        self.min_avg_dollar_volume_20d = min_avg_dollar_volume_20d
        self.intraday_lookback_days = intraday_lookback_days
        self.daily_lookback_days = daily_lookback_days
        self.history_window_bars = history_window_bars
        self.structure_engine = structure_engine or StructureEngine()
        self.zone_engine = zone_engine or ZoneEngine()
        self.pattern_engine = pattern_engine or PatternEngine()

    def prepare_run(self, runner_config: RunnerConfig) -> SyncResult:
        errors: list[str] = []
        with self.session_factory() as session:
            snapshot = self._refresh_universe(session=session, runner_config=runner_config, errors=errors)
            session.commit()

        tickers_to_sync = self._tickers_for_run(snapshot_id=snapshot.id, runner_config=runner_config)
        for ticker in tickers_to_sync:
            try:
                with self.session_factory() as session:
                    symbol = self._ensure_symbol(session, ticker)
                    self._sync_symbol_bars(session=session, symbol=symbol)
                    session.commit()
            except Exception as exc:
                errors.append(f"{ticker}: {exc}")
        return SyncResult(
            snapshot_id=snapshot.id,
            synced_tickers=tickers_to_sync,
            errors=errors,
        )

    def _refresh_universe(
        self,
        *,
        session: Session,
        runner_config: RunnerConfig,
        errors: list[str],
    ) -> UniverseSnapshot:
        session_date, grouped_rows = self._latest_grouped_session()
        snapshot = UniverseSnapshot(
            snapshot_timestamp=datetime.now(timezone.utc),
            refresh_session=UniverseRefreshSession.INTRADAY,
            source=MarketDataSource.POLYGON,
            filters={
                "min_price": str(self.min_price),
                "max_price": str(self.max_price),
                "min_avg_volume_20d": str(self.min_avg_volume_20d),
                "min_avg_dollar_volume_20d": str(self.min_avg_dollar_volume_20d),
            },
            notes=f"Polygon grouped daily refresh for {session_date.isoformat()}",
        )
        session.add(snapshot)
        session.flush()

        grouped_by_ticker = {row.get("T"): row for row in grouped_rows if row.get("T")}
        if runner_config.universe.include_tickers:
            candidate_tickers = list(runner_config.universe.include_tickers)
        else:
            sorted_rows = sorted(
                grouped_rows,
                key=lambda row: Decimal(str((row.get("c") or 0))) * Decimal(str((row.get("v") or 0))),
                reverse=True,
            )
            candidate_tickers = [row["T"] for row in sorted_rows[: self.universe_refresh_limit]]

        for ticker in candidate_tickers:
            try:
                grouped_row = grouped_by_ticker.get(ticker)
                details = self.polygon_client.get_ticker_details(ticker)
                daily_rows = self.polygon_client.get_aggs(
                    ticker=ticker,
                    multiplier=1,
                    timespan="day",
                    from_date=(datetime.now(timezone.utc).date() - timedelta(days=self.daily_lookback_days)),
                    to_date=datetime.now(timezone.utc).date(),
                )
                if not daily_rows:
                    raise ValueError("No daily bars returned.")
                symbol = self._upsert_symbol(session, ticker=ticker, details=details, grouped_row=grouped_row, daily_rows=daily_rows)
                membership = self._build_membership(snapshot_id=snapshot.id, symbol=symbol, grouped_row=grouped_row, daily_rows=daily_rows)
                session.add(membership)
            except Exception as exc:
                errors.append(f"{ticker}: {exc}")

        for ticker in list(ALERT_BENCHMARKS) + list(SECTOR_ETF_MAP.values()):
            try:
                self._ensure_symbol(session, ticker)
            except Exception as exc:
                errors.append(f"{ticker}: {exc}")

        return snapshot

    def _tickers_for_run(self, *, snapshot_id: uuid.UUID, runner_config: RunnerConfig) -> list[str]:
        with self.session_factory() as session:
            memberships = session.scalars(
                select(UniverseMembership)
                .where(
                    UniverseMembership.snapshot_id == snapshot_id,
                    UniverseMembership.hard_eligible.is_(True),
                )
                .order_by(desc(UniverseMembership.avg_dollar_volume_20d), UniverseMembership.symbol_ticker_cache)
            ).all()
            tickers = [
                (membership.symbol_ticker_cache or session.get(Symbol, membership.symbol_id).ticker)
                for membership in memberships
            ]
            if runner_config.universe.include_tickers:
                tickers = [ticker for ticker in tickers if ticker in runner_config.universe.include_tickers]
            tickers = [ticker for ticker in tickers if ticker not in runner_config.universe.exclude_tickers]
            if runner_config.universe.max_symbols_per_run is not None:
                tickers = tickers[: runner_config.universe.max_symbols_per_run]

            sector_etfs: set[str] = set()
            for ticker in tickers:
                symbol = session.scalar(select(Symbol).where(Symbol.ticker == ticker))
                if symbol is None:
                    continue
                sector_etf = symbol.extra.get("sector_etf_ticker")
                if sector_etf:
                    sector_etfs.add(str(sector_etf))
            required = set(tickers)
            required.update(ALERT_BENCHMARKS)
            required.update(sector_etfs)
            return sorted(required)

    def _ensure_symbol(self, session: Session, ticker: str) -> Symbol:
        symbol = session.scalar(select(Symbol).where(Symbol.ticker == ticker))
        if symbol is not None:
            return symbol
        details = self.polygon_client.get_ticker_details(ticker)
        daily_rows = self.polygon_client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_date=(datetime.now(timezone.utc).date() - timedelta(days=self.daily_lookback_days)),
            to_date=datetime.now(timezone.utc).date(),
        )
        if not daily_rows:
            raise ValueError("No daily bars available for symbol bootstrap.")
        symbol = self._upsert_symbol(session, ticker=ticker, details=details, grouped_row=None, daily_rows=daily_rows)
        session.flush()
        return symbol

    def _sync_symbol_bars(self, *, session: Session, symbol: Symbol) -> None:
        today = datetime.now(timezone.utc).date()
        for timeframe, (multiplier, timespan) in self.TIMEFRAME_SPECS.items():
            lookback_days = self.daily_lookback_days if timeframe == Timeframe.DAY_1 else self.intraday_lookback_days
            rows = self.polygon_client.get_aggs(
                ticker=symbol.ticker,
                multiplier=multiplier,
                timespan=timespan,
                from_date=today - timedelta(days=lookback_days),
                to_date=today,
            )
            for row in rows:
                session.execute(self._bar_upsert_statement(symbol.id, timeframe, row))

        for timeframe in (Timeframe.MIN_5, Timeframe.MIN_15, Timeframe.HOUR_1, Timeframe.HOUR_4):
            bars = _load_timeframe_bars(session, symbol.id, timeframe)
            if not bars:
                continue
            structure_history = self.structure_engine.evaluate_history(bars)
            zone_history = self.zone_engine.evaluate_history(bars, structure_history)
            pattern_history = self.pattern_engine.evaluate_history(bars, structure_history=structure_history, zone_history=zone_history)
            for structure_result, zone_result, pattern_result in zip(
                structure_history[-self.history_window_bars :],
                zone_history[-self.history_window_bars :],
                pattern_history[-self.history_window_bars :],
            ):
                upsert_feature_result(session, structure_result)
                upsert_feature_result(session, zone_result)
                upsert_feature_result(session, pattern_result)

    def _upsert_symbol(
        self,
        session: Session,
        *,
        ticker: str,
        details: dict,
        grouped_row: dict | None,
        daily_rows: list[dict],
    ) -> Symbol:
        symbol = session.scalar(select(Symbol).where(Symbol.ticker == ticker))
        if symbol is None:
            symbol = Symbol(
                ticker=ticker,
                polygon_ticker=ticker,
                exchange=self._map_exchange(details),
                security_type=str(details.get("type") or "COMMON_STOCK"),
                country_code="US",
                currency="USD",
                extra={},
            )
            session.add(symbol)
        sector_name = self._infer_sector_name(details)
        last_close = Decimal(str((grouped_row or {}).get("c") or daily_rows[-1].get("c") or 0)).quantize(Decimal("0.0001"))
        symbol.name = str(details.get("name") or ticker)
        symbol.exchange = self._map_exchange(details)
        symbol.security_type = str(details.get("type") or "COMMON_STOCK")
        symbol.country_code = "US"
        symbol.currency = "USD"
        symbol.sector = sector_name
        symbol.industry = str(details.get("sic_description") or details.get("description") or "") or None
        symbol.is_active = bool(details.get("active", True))
        symbol.is_etf = self._is_etf(details)
        symbol.is_otc = bool(details.get("market") == "otc")
        symbol.last_reference_price = last_close
        symbol.last_reference_price_at = _timestamp_from_agg(daily_rows[-1])
        symbol.cik = str(details.get("cik")) if details.get("cik") else None
        symbol.primary_listing = str(details.get("primary_exchange") or "")
        symbol.extra = {
            **symbol.extra,
            "sector_name": sector_name,
            "sector_etf_ticker": SECTOR_ETF_MAP.get(sector_name, "SPY"),
            "sic_description": details.get("sic_description"),
            "description": details.get("description"),
        }
        return symbol

    def _build_membership(
        self,
        *,
        snapshot_id: uuid.UUID,
        symbol: Symbol,
        grouped_row: dict | None,
        daily_rows: list[dict],
    ) -> UniverseMembership:
        last_price = Decimal(str((grouped_row or {}).get("c") or daily_rows[-1].get("c") or 0)).quantize(Decimal("0.0001"))
        recent_rows = daily_rows[-20:]
        avg_volume = (
            sum(Decimal(str(row.get("v") or 0)) for row in recent_rows) / Decimal(max(len(recent_rows), 1))
        ).quantize(Decimal("0.01"))
        avg_dollar_volume = (
            sum(Decimal(str(row.get("c") or 0)) * Decimal(str(row.get("v") or 0)) for row in recent_rows)
            / Decimal(max(len(recent_rows), 1))
        ).quantize(Decimal("0.01"))
        sufficient_history = len(recent_rows) >= 20
        data_quality_ok = all(
            Decimal(str(row.get("c") or 0)) > 0 and Decimal(str(row.get("v") or 0)) >= 0
            for row in recent_rows
        )
        rejection_reasons: list[str] = []
        if symbol.exchange not in {ListedExchange.NYSE, ListedExchange.NASDAQ, ListedExchange.NYSE_ARCA, ListedExchange.AMEX}:
            rejection_reasons.append("EXCHANGE_NOT_ALLOWED")
        if last_price < self.min_price or last_price > self.max_price:
            rejection_reasons.append("PRICE_OUT_OF_RANGE")
        if avg_volume < self.min_avg_volume_20d:
            rejection_reasons.append("AVG_VOLUME_TOO_LOW")
        if avg_dollar_volume < self.min_avg_dollar_volume_20d:
            rejection_reasons.append("AVG_DOLLAR_VOLUME_TOO_LOW")
        if not sufficient_history:
            rejection_reasons.append("INSUFFICIENT_HISTORY")
        if not symbol.is_active:
            rejection_reasons.append("INACTIVE")
        if symbol.is_etf:
            rejection_reasons.append("ETF_EXCLUDED")
        if symbol.is_otc:
            rejection_reasons.append("OTC_EXCLUDED")
        if not data_quality_ok:
            rejection_reasons.append("DATA_QUALITY_FAILED")
        hard_eligible = not rejection_reasons
        if avg_dollar_volume >= Decimal("20000000"):
            tier = UniverseTier.TIER_1
        elif avg_dollar_volume >= Decimal("10000000"):
            tier = UniverseTier.TIER_2
        else:
            tier = UniverseTier.TIER_3
        return UniverseMembership(
            snapshot_id=snapshot_id,
            symbol_id=symbol.id,
            symbol_ticker_cache=symbol.ticker,
            hard_eligible=hard_eligible,
            tier=tier,
            last_price=last_price,
            avg_daily_volume_20d=avg_volume,
            avg_dollar_volume_20d=avg_dollar_volume,
            sufficient_history=sufficient_history,
            data_quality_ok=data_quality_ok,
            rejection_reasons=rejection_reasons,
            quality_flags={"source": "polygon"},
        )

    def _latest_grouped_session(self) -> tuple[date, list[dict]]:
        today = datetime.now(timezone.utc).date()
        for offset in range(0, 7):
            session_date = today - timedelta(days=offset)
            rows = self.polygon_client.get_grouped_daily(session_date)
            if rows:
                return session_date, rows
        raise ValueError("Unable to locate a recent Polygon grouped daily session.")

    def _bar_upsert_statement(self, symbol_id: uuid.UUID, timeframe: Timeframe, row: dict):
        timestamp = _timestamp_from_agg(row)
        known_at = timestamp + timedelta(minutes=15)
        statement = insert(Bar).values(
            symbol_id=symbol_id,
            timeframe=timeframe,
            bar_timestamp=timestamp,
            known_at=known_at,
            open_price=Decimal(str(row.get("o") or 0)).quantize(Decimal("0.0001")),
            high_price=Decimal(str(row.get("h") or 0)).quantize(Decimal("0.0001")),
            low_price=Decimal(str(row.get("l") or 0)).quantize(Decimal("0.0001")),
            close_price=Decimal(str(row.get("c") or 0)).quantize(Decimal("0.0001")),
            volume=int(row.get("v") or 0),
            vwap=Decimal(str(row.get("vw"))).quantize(Decimal("0.0001")) if row.get("vw") is not None else None,
            trade_count=int(row.get("n")) if row.get("n") is not None else None,
            source=MarketDataSource.POLYGON,
            adjustment="SPLIT_ADJUSTED",
        )
        return statement.on_conflict_do_update(
            index_elements=["symbol_id", "timeframe", "bar_timestamp", "adjustment"],
            set_={
                "known_at": statement.excluded.known_at,
                "open_price": statement.excluded.open_price,
                "high_price": statement.excluded.high_price,
                "low_price": statement.excluded.low_price,
                "close_price": statement.excluded.close_price,
                "volume": statement.excluded.volume,
                "vwap": statement.excluded.vwap,
                "trade_count": statement.excluded.trade_count,
            },
        )

    @staticmethod
    def _map_exchange(details: dict) -> ListedExchange:
        value = str(details.get("primary_exchange") or "").upper()
        if "XNAS" in value or "NASDAQ" in value:
            return ListedExchange.NASDAQ
        if "ARCX" in value or "ARCA" in value:
            return ListedExchange.NYSE_ARCA
        if "ASE" in value or "AMEX" in value:
            return ListedExchange.AMEX
        return ListedExchange.NYSE

    @staticmethod
    def _is_etf(details: dict) -> bool:
        type_value = str(details.get("type") or "").upper()
        name_value = str(details.get("name") or "").upper()
        return "ETF" in type_value or " ETF " in f" {name_value} "

    @staticmethod
    def _infer_sector_name(details: dict) -> str:
        haystack = " ".join(
            [
                str(details.get("sic_description") or ""),
                str(details.get("description") or ""),
                str(details.get("name") or ""),
            ]
        ).lower()
        if any(keyword in haystack for keyword in ("software", "semiconductor", "technology", "internet", "hardware")):
            return "Technology"
        if any(keyword in haystack for keyword in ("bank", "financial", "insurance", "capital markets")):
            return "Financials"
        if any(keyword in haystack for keyword in ("health", "medical", "biotech", "pharma", "drug")):
            return "Healthcare"
        if any(keyword in haystack for keyword in ("energy", "oil", "gas", "drilling")):
            return "Energy"
        if any(keyword in haystack for keyword in ("utility", "power", "electric")):
            return "Utilities"
        if any(keyword in haystack for keyword in ("retail", "consumer", "restaurant", "auto")):
            return "Consumer Discretionary"
        if any(keyword in haystack for keyword in ("food", "beverage", "grocery", "staple")):
            return "Consumer Staples"
        if any(keyword in haystack for keyword in ("industrial", "aerospace", "transport", "machinery")):
            return "Industrials"
        if any(keyword in haystack for keyword in ("material", "chemical", "mining", "metal")):
            return "Materials"
        if any(keyword in haystack for keyword in ("reit", "real estate", "property")):
            return "Real Estate"
        if any(keyword in haystack for keyword in ("telecom", "communication", "media", "broadcast")):
            return "Communication Services"
        return "Unknown"


def _load_timeframe_bars(session: Session, symbol_id: uuid.UUID, timeframe: Timeframe) -> list[EngineBar]:
    rows = session.scalars(
        select(Bar)
        .where(Bar.symbol_id == symbol_id, Bar.timeframe == timeframe)
        .order_by(Bar.bar_timestamp)
    ).all()
    return [
        EngineBar(
            symbol_id=row.symbol_id,
            timeframe=row.timeframe.value,
            bar_timestamp=row.bar_timestamp,
            known_at=row.known_at,
            open_price=row.open_price,
            high_price=row.high_price,
            low_price=row.low_price,
            close_price=row.close_price,
            volume=row.volume,
        )
        for row in rows
    ]


def _timestamp_from_agg(row: dict) -> datetime:
    return datetime.fromtimestamp(int(row["t"]) / 1000, tz=timezone.utc)


__all__ = [
    "ConfiguredHaltStatusProvider",
    "DbMarketDataLoader",
    "DbPhase2FeatureLoader",
    "DbRegimeExternalInputLoader",
    "DbUniverseContextLoader",
    "PolygonEventRiskInputLoader",
    "PolygonSyncService",
    "SqlitePriorAlertStateLoader",
    "SyncResult",
]
