from __future__ import annotations

import math
import statistics
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.alerts.models import PriorAlertState
from doctrine_engine.db.models.features import Feature
from doctrine_engine.db.models.market_data import Bar
from doctrine_engine.db.models.symbols import Symbol, UniverseMembership, UniverseSnapshot
from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    PatternEvent,
    RecontainmentResult,
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.persistence import (
    FEATURE_SET_PATTERN,
    FEATURE_SET_STRUCTURE,
    FEATURE_SET_ZONE,
    FEATURE_VERSION_V1,
)
from doctrine_engine.event_risk.models import (
    CorporateEventInput,
    EarningsCalendarInput,
    EventRiskEngineInput,
    HaltRiskInput,
    NewsRiskInput,
)
from doctrine_engine.product.clients import PolygonApiError, PolygonClient
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.regime.models import (
    BreadthInput,
    RegimeEngineInput,
    RegimeIndexInput,
    SectorRegimeInput,
    StockRelativeRegimeInput,
    VolatilityInput,
)
from doctrine_engine.runner.adapters import (
    EventRiskExternalInputLoader,
    MarketDataLoader,
    Phase2FeatureLoader,
    PriorAlertStateLoader,
    RegimeExternalInputLoader,
    UniverseContextLoader,
)
from doctrine_engine.runner.models import (
    BenchmarkPhaseContext,
    PersistedFramePhase2Context,
    PersistedPhase2Context,
    RunnerInput,
    SymbolMarketContext,
    UniverseSymbolContext,
)


def _timeframe_db_value(timeframe: Timeframe) -> str:
    return timeframe.value

ALERT_BENCHMARKS = ("SPY", "QQQ", "IWM")
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Consumer Staples": "XLP",
    "Consumer Discretionary": "XLY",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Unknown": "SPY",
}


class HaltStatusProvider(Protocol):
    def load(
        self,
        *,
        ticker: str,
        signal_timestamp: datetime,
        known_at_baseline: datetime,
        news_halt_risk: HaltRiskInput | None,
    ) -> HaltRiskInput | None: ...


class DbUniverseContextLoader(UniverseContextLoader):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def load(self, runner_input: RunnerInput) -> list[UniverseSymbolContext]:
        with self.session_factory() as session:
            snapshot = session.scalar(
                select(UniverseSnapshot)
                .order_by(desc(UniverseSnapshot.snapshot_timestamp), desc(UniverseSnapshot.created_at))
                .limit(1)
            )
            if snapshot is None:
                return []
            memberships = session.scalars(
                select(UniverseMembership)
                .where(
                    UniverseMembership.snapshot_id == snapshot.id,
                    UniverseMembership.hard_eligible.is_(True),
                )
                .order_by(desc(UniverseMembership.avg_dollar_volume_20d), UniverseMembership.symbol_ticker_cache)
            ).all()
            contexts: list[UniverseSymbolContext] = []
            for membership in memberships:
                symbol = session.get(Symbol, membership.symbol_id)
                if symbol is None:
                    continue
                contexts.append(
                    UniverseSymbolContext(
                        symbol_id=symbol.id,
                        ticker=symbol.ticker,
                        universe_snapshot_id=snapshot.id,
                        universe_eligible=membership.hard_eligible,
                        price_reference=membership.last_price or symbol.last_reference_price or Decimal("0"),
                        universe_reason_codes=list(membership.rejection_reasons),
                        universe_known_at=snapshot.snapshot_timestamp,
                    )
                )
            return contexts


class DbMarketDataLoader(MarketDataLoader):
    def __init__(self, session_factory: sessionmaker[Session], history_window_bars: int) -> None:
        self.session_factory = session_factory
        self.history_window_bars = history_window_bars

    def load_symbol_context(self, symbol: UniverseSymbolContext, runner_input: RunnerInput) -> SymbolMarketContext:
        with self.session_factory() as session:
            return SymbolMarketContext(
                htf_bar=self._load_latest_bar(session, symbol.symbol_id, Timeframe.HOUR_4),
                mtf_bar=self._load_latest_bar(session, symbol.symbol_id, Timeframe.HOUR_1),
                ltf_bar=self._load_latest_bar(session, symbol.symbol_id, Timeframe.MIN_15),
                micro_bar=(
                    self._load_latest_bar(session, symbol.symbol_id, Timeframe.MIN_5)
                    if runner_input.config.require_micro_confirmation or runner_input.config.timeframes.micro is not None
                    else None
                ),
            )

    def load_benchmark_context(self, runner_input: RunnerInput) -> BenchmarkPhaseContext:
        with self.session_factory() as session:
            market_indexes = [self._load_regime_index_input(session, ticker) for ticker in ALERT_BENCHMARKS]
        return BenchmarkPhaseContext(market_indexes=market_indexes)

    def _load_regime_index_input(self, session: Session, ticker: str) -> RegimeIndexInput:
        symbol = self._require_symbol(session, ticker)
        frame = _load_frame_context(
            session=session,
            symbol_id=symbol.id,
            timeframe=Timeframe.HOUR_4,
            history_window_bars=self.history_window_bars,
        )
        if frame is None:
            raise ValueError(f"Persisted Phase 2 context missing for benchmark {ticker}.")
        latest_bar = self._load_latest_bar(session, symbol.id, Timeframe.HOUR_4)
        if latest_bar is None:
            raise ValueError(f"Latest HTF bar missing for benchmark {ticker}.")
        return RegimeIndexInput(
            ticker=ticker,
            latest_bar=latest_bar,
            structure=frame.structure,
            zone=frame.zone,
            pattern=frame.pattern,
            structure_history=frame.structure_history,
        )

    @staticmethod
    def _load_latest_bar(session: Session, symbol_id: uuid.UUID, timeframe: Timeframe) -> EngineBar | None:
        row = session.scalar(
            select(Bar)
            .where(Bar.symbol_id == symbol_id, Bar.timeframe == _timeframe_db_value(timeframe))
            .order_by(desc(Bar.bar_timestamp))
            .limit(1)
        )
        if row is None:
            return None
        return _bar_to_engine_bar(row)

    @staticmethod
    def _require_symbol(session: Session, ticker: str) -> Symbol:
        symbol = session.scalar(select(Symbol).where(Symbol.ticker == ticker))
        if symbol is None:
            raise ValueError(f"Required symbol {ticker} missing from symbols table.")
        return symbol


class DbPhase2FeatureLoader(Phase2FeatureLoader):
    def __init__(self, session_factory: sessionmaker[Session], history_window_bars: int) -> None:
        self.session_factory = session_factory
        self.history_window_bars = history_window_bars

    def load(self, symbol: UniverseSymbolContext, runner_input: RunnerInput) -> PersistedPhase2Context | None:
        with self.session_factory() as session:
            htf = _load_frame_context(session=session, symbol_id=symbol.symbol_id, timeframe=Timeframe.HOUR_4, history_window_bars=self.history_window_bars)
            mtf = _load_frame_context(session=session, symbol_id=symbol.symbol_id, timeframe=Timeframe.HOUR_1, history_window_bars=self.history_window_bars)
            ltf = _load_frame_context(session=session, symbol_id=symbol.symbol_id, timeframe=Timeframe.MIN_15, history_window_bars=self.history_window_bars)
            if htf is None or mtf is None or ltf is None:
                return None
            micro = None
            if runner_input.config.require_micro_confirmation or runner_input.config.timeframes.micro is not None:
                micro = _load_frame_context(
                    session=session,
                    symbol_id=symbol.symbol_id,
                    timeframe=Timeframe.MIN_5,
                    history_window_bars=self.history_window_bars,
                )
                if micro is None:
                    return None
            return PersistedPhase2Context(htf=htf, mtf=mtf, ltf=ltf, micro=micro)


class DbRegimeExternalInputLoader(RegimeExternalInputLoader):
    def __init__(self, session_factory: sessionmaker[Session], history_window_bars: int) -> None:
        self.session_factory = session_factory
        self.history_window_bars = history_window_bars

    def load(
        self,
        symbol: UniverseSymbolContext,
        benchmark_context: BenchmarkPhaseContext,
        runner_input: RunnerInput,
    ) -> RegimeEngineInput:
        with self.session_factory() as session:
            symbol_row = session.get(Symbol, symbol.symbol_id)
            if symbol_row is None:
                raise ValueError(f"Symbol {symbol.ticker} missing from symbols table.")

            sector_name = str(symbol_row.extra.get("sector_name") or symbol_row.sector or "Unknown")
            sector_etf_ticker = str(symbol_row.extra.get("sector_etf_ticker") or SECTOR_ETF_MAP.get(sector_name, "SPY"))
            sector_symbol = session.scalar(select(Symbol).where(Symbol.ticker == sector_etf_ticker))
            if sector_symbol is None:
                raise ValueError(f"Sector ETF {sector_etf_ticker} missing for {symbol.ticker}.")

            sector_frame = _load_frame_context(
                session=session,
                symbol_id=sector_symbol.id,
                timeframe=Timeframe.HOUR_4,
                history_window_bars=self.history_window_bars,
            )
            sector_bar = DbMarketDataLoader._load_latest_bar(session, sector_symbol.id, Timeframe.HOUR_4)
            if sector_frame is None or sector_bar is None:
                raise ValueError(f"Sector context missing for {symbol.ticker} ({sector_etf_ticker}).")

            stock_daily = _load_recent_bars(session, symbol.symbol_id, Timeframe.DAY_1, 30)
            spy_symbol = session.scalar(select(Symbol).where(Symbol.ticker == "SPY"))
            if spy_symbol is None:
                raise ValueError("SPY symbol missing for regime context.")
            spy_daily = _load_recent_bars(session, spy_symbol.id, Timeframe.DAY_1, 30)
            sector_daily = _load_recent_bars(session, sector_symbol.id, Timeframe.DAY_1, 30)
            stock_latest_bar = stock_daily[-1] if stock_daily else DbMarketDataLoader._load_latest_bar(session, symbol.symbol_id, Timeframe.HOUR_4)
            if stock_latest_bar is None:
                raise ValueError(f"Daily or HTF bars missing for {symbol.ticker}.")

            return RegimeEngineInput(
                market_indexes=list(benchmark_context.market_indexes),
                sector=SectorRegimeInput(
                    sector_name=sector_name,
                    sector_etf_ticker=sector_etf_ticker,
                    latest_bar=sector_bar,
                    structure=sector_frame.structure,
                    zone=sector_frame.zone,
                    pattern=sector_frame.pattern,
                    structure_history=sector_frame.structure_history,
                    relative_strength_vs_spy=_relative_strength_from_bars(sector_daily, spy_daily),
                    momentum_persistence_score=_momentum_persistence_score(sector_daily),
                ),
                stock_relative=StockRelativeRegimeInput(
                    symbol_id=symbol.symbol_id,
                    ticker=symbol.ticker,
                    sector_name=sector_name,
                    latest_bar=stock_latest_bar,
                    relative_strength_vs_spy=_relative_strength_from_bars(stock_daily, spy_daily),
                    relative_strength_vs_sector=_relative_strength_from_bars(stock_daily, sector_daily),
                    structure_quality_score=None,
                ),
                breadth=_compute_breadth(session),
                volatility=_compute_volatility(spy_daily),
            )


class PolygonEventRiskInputLoader(EventRiskExternalInputLoader):
    CORPORATE_KEYWORDS = {
        "OFFERING": ["offering", "secondary offering", "public offering"],
        "DILUTION": ["dilution", "dilutive", "atm program"],
        "GUIDANCE": ["guidance", "forecast", "outlook"],
        "FDA_REGULATORY": ["fda", "regulatory", "clinical hold", "trial halt"],
        "MAJOR_CORPORATE_ANNOUNCEMENT": ["merger", "acquisition", "buyout", "bankruptcy", "restructuring"],
    }
    ABNORMAL_NEWS_KEYWORDS = ["unusual volume", "volume spike", "surge in volume", "heavy volume"]
    UNCLEAR_BINARY_KEYWORDS = [
        "trial data",
        "approval",
        "rejection",
        "guidance",
        "offering",
        "dilution",
        "regulatory",
        "earnings",
        "merger",
        "acquisition",
    ]
    HALT_KEYWORDS = ["trading halt", "halted", "volatility halt"]

    def __init__(
        self,
        *,
        polygon_client: PolygonClient,
        news_lookback_hours: int,
        news_limit: int,
        halt_status_provider: HaltStatusProvider,
    ) -> None:
        self.polygon_client = polygon_client
        self.news_lookback_hours = news_lookback_hours
        self.news_limit = news_limit
        self.halt_status_provider = halt_status_provider

    def load(
        self,
        symbol: UniverseSymbolContext,
        signal_time_baseline: datetime,
        known_at_baseline: datetime,
        runner_input: RunnerInput,
    ) -> EventRiskEngineInput:
        earnings = self._load_earnings(symbol.ticker, signal_time_baseline, known_at_baseline)
        corporate_events, news_risks, news_halt = self._load_news(symbol.ticker, signal_time_baseline, known_at_baseline)
        halt_risk = self.halt_status_provider.load(
            ticker=symbol.ticker,
            signal_timestamp=signal_time_baseline,
            known_at_baseline=known_at_baseline,
            news_halt_risk=news_halt,
        )
        return EventRiskEngineInput(
            symbol_id=symbol.symbol_id,
            ticker=symbol.ticker,
            signal_timestamp=signal_time_baseline,
            known_at=known_at_baseline,
            earnings=earnings,
            corporate_events=corporate_events,
            news_risks=news_risks,
            halt_risk=halt_risk,
        )

    def _load_earnings(
        self,
        ticker: str,
        signal_time_baseline: datetime,
        known_at_baseline: datetime,
    ) -> EarningsCalendarInput | None:
        try:
            rows = self.polygon_client.get_earnings(
                ticker=ticker,
                date_gte=(signal_time_baseline - timedelta(days=7)).date(),
                date_lte=(signal_time_baseline + timedelta(days=7)).date(),
                limit=10,
            )
        except PolygonApiError:
            return None
        if not rows:
            return EarningsCalendarInput(
                ticker=ticker,
                earnings_datetime=None,
                known_at=known_at_baseline,
                source="polygon_benzinga",
            )
        earnings_dt = None
        for row in rows:
            date_text = row.get("date") or row.get("report_date")
            time_text = str(row.get("time") or "").lower()
            candidate = _parse_date(date_text)
            if candidate is None:
                continue
            base_dt = datetime.combine(candidate, datetime.min.time(), tzinfo=timezone.utc)
            if time_text in {"after market close", "amc"}:
                earnings_dt = base_dt + timedelta(hours=20)
            elif time_text in {"before market open", "bmo"}:
                earnings_dt = base_dt + timedelta(hours=12)
            else:
                earnings_dt = base_dt + timedelta(hours=16)
            break
        return EarningsCalendarInput(
            ticker=ticker,
            earnings_datetime=earnings_dt,
            known_at=known_at_baseline,
            source="polygon_benzinga",
        )

    def _load_news(
        self,
        ticker: str,
        signal_time_baseline: datetime,
        known_at_baseline: datetime,
    ) -> tuple[list[CorporateEventInput] | None, list[NewsRiskInput] | None, HaltRiskInput | None]:
        try:
            rows = self.polygon_client.get_news(
                ticker=ticker,
                published_gte=signal_time_baseline - timedelta(hours=self.news_lookback_hours),
                published_lte=signal_time_baseline,
                limit=self.news_limit,
            )
        except PolygonApiError:
            return None, None, None

        corporate_events: list[CorporateEventInput] = []
        news_risks: list[NewsRiskInput] = []
        halt_risk: HaltRiskInput | None = None
        for row in rows:
            published = _parse_datetime(row.get("published_utc"))
            if published is None or published > known_at_baseline:
                continue
            haystack = " ".join(
                [
                    str(row.get("title") or ""),
                    str(row.get("description") or ""),
                    " ".join(str(item) for item in row.get("keywords") or []),
                ]
            ).lower()
            if any(keyword in haystack for keyword in self.ABNORMAL_NEWS_KEYWORDS):
                news_risks.append(
                    NewsRiskInput(
                        category="ABNORMAL_VOLUME_NEWS",
                        event_datetime=published,
                        known_at=published,
                        severity_score=Decimal("0.50"),
                        source="polygon_news",
                    )
                )
            if any(keyword in haystack for keyword in self.UNCLEAR_BINARY_KEYWORDS):
                news_risks.append(
                    NewsRiskInput(
                        category="UNCLEAR_BINARY_NEWS",
                        event_datetime=published,
                        known_at=published,
                        severity_score=Decimal("0.50"),
                        source="polygon_news",
                    )
                )
            for event_type, keywords in self.CORPORATE_KEYWORDS.items():
                if any(keyword in haystack for keyword in keywords):
                    corporate_events.append(
                        CorporateEventInput(
                            event_type=event_type,
                            event_datetime=published,
                            known_at=published,
                            source="polygon_news",
                            blocks_longs=True,
                        )
                    )
                    break
            if halt_risk is None and any(keyword in haystack for keyword in self.HALT_KEYWORDS):
                halt_risk = HaltRiskInput(
                    halt_detected=True,
                    halt_datetime=published,
                    known_at=published,
                    source="polygon_news",
                )
        return corporate_events, news_risks, halt_risk


class ConfiguredHaltStatusProvider(HaltStatusProvider):
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def load(
        self,
        *,
        ticker: str,
        signal_timestamp: datetime,
        known_at_baseline: datetime,
        news_halt_risk: HaltRiskInput | None,
    ) -> HaltRiskInput | None:
        if news_halt_risk is not None:
            return news_halt_risk
        if self.mode == "fail_closed":
            return HaltRiskInput(
                halt_detected=True,
                halt_datetime=signal_timestamp,
                known_at=known_at_baseline,
                source="configured_no_data_fail_closed",
            )
        return None


class SqlitePriorAlertStateLoader(PriorAlertStateLoader):
    def __init__(self, state_store: OperationalStateStore) -> None:
        self.state_store = state_store

    def load(self, symbol_id: uuid.UUID, setup_state: str, entry_type: str) -> PriorAlertState | None:
        return self.state_store.load_prior_alert_state(symbol_id, setup_state, entry_type)


def _load_frame_context(
    *,
    session: Session,
    symbol_id: uuid.UUID,
    timeframe: Timeframe,
    history_window_bars: int,
) -> PersistedFramePhase2Context | None:
    structure_rows = list(
        session.scalars(
            select(Feature)
                .where(
                    Feature.symbol_id == symbol_id,
                    Feature.timeframe == _timeframe_db_value(timeframe),
                    Feature.feature_set == FEATURE_SET_STRUCTURE,
                    Feature.feature_version == FEATURE_VERSION_V1,
                )
            .order_by(desc(Feature.bar_timestamp))
            .limit(history_window_bars)
        ).all()
    )
    if not structure_rows:
        return None
    structure_rows.reverse()
    latest_bar_timestamp = structure_rows[-1].bar_timestamp
    zone_row = session.scalar(
        select(Feature).where(
            Feature.symbol_id == symbol_id,
            Feature.timeframe == _timeframe_db_value(timeframe),
            Feature.feature_set == FEATURE_SET_ZONE,
            Feature.feature_version == FEATURE_VERSION_V1,
            Feature.bar_timestamp == latest_bar_timestamp,
        )
    )
    pattern_row = session.scalar(
        select(Feature).where(
            Feature.symbol_id == symbol_id,
            Feature.timeframe == _timeframe_db_value(timeframe),
            Feature.feature_set == FEATURE_SET_PATTERN,
            Feature.feature_version == FEATURE_VERSION_V1,
            Feature.bar_timestamp == latest_bar_timestamp,
        )
    )
    if zone_row is None or pattern_row is None:
        return None
    structure_history = [_deserialize_structure_result(row) for row in structure_rows]
    return PersistedFramePhase2Context(
        structure=structure_history[-1],
        structure_history=structure_history,
        zone=_deserialize_zone_result(zone_row),
        pattern=_deserialize_pattern_result(pattern_row),
    )


def _load_recent_bars(session: Session, symbol_id: uuid.UUID, timeframe: Timeframe, limit: int) -> list[EngineBar]:
    rows = list(
        session.scalars(
            select(Bar)
            .where(Bar.symbol_id == symbol_id, Bar.timeframe == _timeframe_db_value(timeframe))
            .order_by(desc(Bar.bar_timestamp))
            .limit(limit)
        ).all()
    )
    rows.reverse()
    return [_bar_to_engine_bar(row) for row in rows]


def _compute_breadth(session: Session) -> BreadthInput | None:
    snapshot = session.scalar(
        select(UniverseSnapshot)
        .order_by(desc(UniverseSnapshot.snapshot_timestamp), desc(UniverseSnapshot.created_at))
        .limit(1)
    )
    if snapshot is None:
        return None
    memberships = session.scalars(
        select(UniverseMembership).where(
            UniverseMembership.snapshot_id == snapshot.id,
            UniverseMembership.hard_eligible.is_(True),
        )
    ).all()
    advances = 0
    declines = 0
    up_volume = Decimal("0")
    total_volume = Decimal("0")
    latest_known_at = snapshot.snapshot_timestamp
    for membership in memberships:
        bars = _load_recent_bars(session, membership.symbol_id, Timeframe.DAY_1, 2)
        if len(bars) < 2:
            continue
        previous_bar, latest_bar = bars[-2], bars[-1]
        latest_known_at = max(latest_known_at, latest_bar.known_at)
        total_volume += Decimal(latest_bar.volume)
        if latest_bar.close_price > previous_bar.close_price:
            advances += 1
            up_volume += Decimal(latest_bar.volume)
        elif latest_bar.close_price < previous_bar.close_price:
            declines += 1
    if advances == 0 and declines == 0:
        return None
    advance_decline_ratio = (
        Decimal(advances)
        if declines == 0
        else (Decimal(advances) / Decimal(declines)).quantize(Decimal("0.0000"))
    )
    up_volume_ratio = (
        (up_volume / total_volume).quantize(Decimal("0.0000"))
        if total_volume > 0
        else None
    )
    return BreadthInput(
        advance_decline_ratio=advance_decline_ratio,
        up_volume_ratio=up_volume_ratio,
        known_at=latest_known_at,
    )


def _compute_volatility(spy_daily: list[EngineBar]) -> VolatilityInput | None:
    if len(spy_daily) < 21:
        return None
    closes = [float(bar.close_price) for bar in spy_daily]
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
        if closes[index] > 0 and closes[index - 1] > 0
    ]
    if len(returns) < 20:
        return None
    rv20 = Decimal(str(statistics.pstdev(returns[-20:]) * math.sqrt(252))).quantize(Decimal("0.0000"))
    rv5 = Decimal(str(statistics.pstdev(returns[-5:]) * math.sqrt(252))).quantize(Decimal("0.0000"))
    return VolatilityInput(
        realized_volatility_20d=rv20,
        realized_volatility_5d=rv5,
        known_at=spy_daily[-1].known_at,
    )


def _relative_strength_from_bars(lhs: list[EngineBar], rhs: list[EngineBar]) -> Decimal | None:
    if len(lhs) < 2 or len(rhs) < 2:
        return None
    lhs_return = (lhs[-1].close_price / lhs[0].close_price) - Decimal("1")
    rhs_return = (rhs[-1].close_price / rhs[0].close_price) - Decimal("1")
    return (lhs_return - rhs_return).quantize(Decimal("0.0000"))


def _momentum_persistence_score(bars: list[EngineBar]) -> Decimal | None:
    if len(bars) < 6:
        return None
    positives = 0
    comparisons = 0
    for previous_bar, current_bar in zip(bars[-6:-1], bars[-5:]):
        comparisons += 1
        if current_bar.close_price >= previous_bar.close_price:
            positives += 1
    return (Decimal(positives) / Decimal(comparisons)).quantize(Decimal("0.0000"))


def _deserialize_structure_result(feature: Feature) -> StructureEngineResult:
    payload = feature.values
    references = payload["reference_levels"]
    return StructureEngineResult(
        symbol_id=feature.symbol_id,
        timeframe=feature.timeframe.value,
        bar_timestamp=feature.bar_timestamp,
        known_at=feature.known_at,
        config_version=payload["config_version"],
        pivot_window=int(payload["pivot_window"]),
        swing_points=[
            SwingPoint(
                kind=item["kind"],
                pivot_timestamp=_parse_datetime(item["pivot_timestamp"]),
                confirmed_at=_parse_datetime(item["confirmed_at"]),
                price=Decimal(item["price"]),
                sequence_index=int(item["sequence_index"]),
            )
            for item in payload["swing_points"]
        ],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=_decimal_or_none(references["bullish_bos_reference_price"]),
            bullish_bos_reference_timestamp=_parse_datetime(references["bullish_bos_reference_timestamp"]),
            bullish_bos_protected_low_price=_decimal_or_none(references["bullish_bos_protected_low_price"]),
            bullish_bos_protected_low_timestamp=_parse_datetime(references["bullish_bos_protected_low_timestamp"]),
            bearish_bos_reference_price=_decimal_or_none(references["bearish_bos_reference_price"]),
            bearish_bos_reference_timestamp=_parse_datetime(references["bearish_bos_reference_timestamp"]),
            bearish_bos_protected_high_price=_decimal_or_none(references["bearish_bos_protected_high_price"]),
            bearish_bos_protected_high_timestamp=_parse_datetime(references["bearish_bos_protected_high_timestamp"]),
            bullish_choch_reference_price=_decimal_or_none(references["bullish_choch_reference_price"]),
            bullish_choch_reference_timestamp=_parse_datetime(references["bullish_choch_reference_timestamp"]),
            bearish_choch_reference_price=_decimal_or_none(references["bearish_choch_reference_price"]),
            bearish_choch_reference_timestamp=_parse_datetime(references["bearish_choch_reference_timestamp"]),
        ),
        active_range_selection=payload["active_range_selection"],
        active_range_low=_decimal_or_none(payload["active_range_low"]),
        active_range_low_timestamp=_parse_datetime(payload["active_range_low_timestamp"]),
        active_range_high=_decimal_or_none(payload["active_range_high"]),
        active_range_high_timestamp=_parse_datetime(payload["active_range_high_timestamp"]),
        trend_state=payload["trend_state"],
        events_on_bar=[
            StructureEvent(
                event_type=item["event_type"],
                event_timestamp=_parse_datetime(item["event_timestamp"]),
                reference_timestamp=_parse_datetime(item["reference_timestamp"]),
                reference_price=Decimal(item["reference_price"]),
                close_price=Decimal(item["close_price"]),
            )
            for item in payload["events_on_bar"]
        ],
    )


def _deserialize_zone_result(feature: Feature) -> ZoneEngineResult:
    payload = feature.values
    return ZoneEngineResult(
        symbol_id=feature.symbol_id,
        timeframe=feature.timeframe.value,
        bar_timestamp=feature.bar_timestamp,
        known_at=feature.known_at,
        config_version=payload["config_version"],
        range_status=payload["range_status"],
        selection_reason=payload["selection_reason"],
        active_swing_low=_decimal_or_none(payload["active_swing_low"]),
        active_swing_low_timestamp=_parse_datetime(payload["active_swing_low_timestamp"]),
        active_swing_high=_decimal_or_none(payload["active_swing_high"]),
        active_swing_high_timestamp=_parse_datetime(payload["active_swing_high_timestamp"]),
        range_width=_decimal_or_none(payload["range_width"]),
        equilibrium=_decimal_or_none(payload["equilibrium"]),
        equilibrium_band_low=_decimal_or_none(payload["equilibrium_band_low"]),
        equilibrium_band_high=_decimal_or_none(payload["equilibrium_band_high"]),
        zone_location=payload["zone_location"],
        distance_from_equilibrium=_decimal_or_none(payload["distance_from_equilibrium"]),
        distance_from_equilibrium_pct_of_range=_decimal_or_none(payload["distance_from_equilibrium_pct_of_range"]),
    )


def _deserialize_pattern_result(feature: Feature) -> PatternEngineResult:
    payload = feature.values
    return PatternEngineResult(
        symbol_id=feature.symbol_id,
        timeframe=feature.timeframe.value,
        bar_timestamp=feature.bar_timestamp,
        known_at=feature.known_at,
        config_version=payload["config_version"],
        compression=CompressionResult(
            status=payload["compression"]["status"],
            criteria_met=list(payload["compression"]["criteria_met"]),
            lookback_bars=int(payload["compression"]["lookback_bars"]),
        ),
        bullish_displacement=DisplacementResult(
            status=payload["bullish_displacement"]["status"],
            mode=payload["bullish_displacement"]["mode"],
            event_timestamp=_parse_datetime(payload["bullish_displacement"]["event_timestamp"]),
            reference_price=_decimal_or_none(payload["bullish_displacement"]["reference_price"]),
            reference_timestamp=_parse_datetime(payload["bullish_displacement"]["reference_timestamp"]),
            range_multiple_atr=_decimal_or_none(payload["bullish_displacement"]["range_multiple_atr"]),
            close_location_ratio=_decimal_or_none(payload["bullish_displacement"]["close_location_ratio"]),
        ),
        bullish_reclaim=_deserialize_lifecycle(payload["bullish_reclaim"]),
        bullish_fake_breakdown=_deserialize_lifecycle(payload["bullish_fake_breakdown"]),
        bullish_trap_reverse=TrapReverseResult(
            status=payload["bullish_trap_reverse"]["status"],
            reference_price=_decimal_or_none(payload["bullish_trap_reverse"]["reference_price"]),
            reference_timestamp=_parse_datetime(payload["bullish_trap_reverse"]["reference_timestamp"]),
            trigger_event=payload["bullish_trap_reverse"]["trigger_event"],
            event_timestamp=_parse_datetime(payload["bullish_trap_reverse"]["event_timestamp"]),
        ),
        recontainment=RecontainmentResult(
            status=payload["recontainment"]["status"],
            source_displacement_timestamp=_parse_datetime(payload["recontainment"]["source_displacement_timestamp"]),
            source_displacement_reference_price=_decimal_or_none(payload["recontainment"]["source_displacement_reference_price"]),
            candidate_start_timestamp=_parse_datetime(payload["recontainment"]["candidate_start_timestamp"]),
            active_range_low=_decimal_or_none(payload["recontainment"]["active_range_low"]),
            active_range_high=_decimal_or_none(payload["recontainment"]["active_range_high"]),
        ),
        events_on_bar=[
            PatternEvent(
                event_type=item["event_type"],
                event_timestamp=_parse_datetime(item["event_timestamp"]),
                reference_timestamp=_parse_datetime(item["reference_timestamp"]),
                reference_price=_decimal_or_none(item["reference_price"]),
            )
            for item in payload["events_on_bar"]
        ],
        active_flags=list(payload["active_flags"]),
    )


def _deserialize_lifecycle(payload: dict) -> LifecyclePatternResult:
    return LifecyclePatternResult(
        status=payload["status"],
        reference_price=_decimal_or_none(payload["reference_price"]),
        reference_timestamp=_parse_datetime(payload["reference_timestamp"]),
        sweep_low=_decimal_or_none(payload["sweep_low"]),
        candidate_start_timestamp=_parse_datetime(payload["candidate_start_timestamp"]),
        event_timestamp=_parse_datetime(payload["event_timestamp"]),
    )


def _bar_to_engine_bar(row: Bar) -> EngineBar:
    return EngineBar(
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


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _decimal_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


__all__ = [
    "ConfiguredHaltStatusProvider",
    "DbMarketDataLoader",
    "DbPhase2FeatureLoader",
    "DbRegimeExternalInputLoader",
    "DbUniverseContextLoader",
    "PolygonEventRiskInputLoader",
    "SqlitePriorAlertStateLoader",
]
