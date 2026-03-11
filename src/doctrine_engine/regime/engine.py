from __future__ import annotations

from decimal import Decimal

from doctrine_engine.regime.models import (
    BreadthInput,
    RegimeEngineConfig,
    RegimeEngineInput,
    RegimeEngineResult,
    RegimeIndexInput,
    SectorRegimeInput,
    VolatilityInput,
)


class RegimeEngine:
    def __init__(self, config: RegimeEngineConfig | None = None) -> None:
        self.config = config or RegimeEngineConfig()

    def evaluate(self, regime_input: RegimeEngineInput) -> RegimeEngineResult:
        indexes = self._validate_input(regime_input)
        breadth_complete = self._breadth_complete(regime_input.breadth)
        volatility_complete = self._volatility_complete(regime_input.volatility)
        coverage_complete = breadth_complete and volatility_complete

        market_components = {
            index.ticker: self._index_directional_component(index)
            for index in indexes.values()
        }
        market_trend_score = sum(market_components.values())

        breadth_strong = self._breadth_strong(regime_input.breadth)
        breadth_weak = self._breadth_weak(regime_input.breadth)
        high_vol = self._high_vol(regime_input.volatility)
        risk_off_vol = self._risk_off_vol(regime_input.volatility)

        market_regime = self._classify_market_regime(
            market_trend_score=market_trend_score,
            breadth_weak=breadth_weak,
            high_vol=high_vol,
            risk_off_vol=risk_off_vol,
        )

        sector_direction = self._sector_direction(regime_input.sector)
        sector_rs_supportive = self._sector_rs_supportive(regime_input.sector)
        sector_rs_hostile = self._sector_rs_hostile(regime_input.sector)
        momentum_supportive = self._momentum_supportive(regime_input.sector)
        momentum_hostile = self._momentum_hostile(regime_input.sector)

        sector_regime = self._classify_sector_regime(
            sector_direction=sector_direction,
            sector_rs_supportive=sector_rs_supportive,
            sector_rs_hostile=sector_rs_hostile,
            momentum_supportive=momentum_supportive,
            momentum_hostile=momentum_hostile,
        )

        market_permission_score = self._market_permission_score(
            market_trend_score=market_trend_score,
            breadth_strong=breadth_strong,
            breadth_weak=breadth_weak,
            high_vol=high_vol,
            risk_off_vol=risk_off_vol,
        )
        sector_permission_score = self._sector_permission_score(
            sector_direction=sector_direction,
            sector_rs_supportive=sector_rs_supportive,
            sector_rs_hostile=sector_rs_hostile,
            momentum_supportive=momentum_supportive,
            momentum_hostile=momentum_hostile,
        )

        allows_longs = self._allows_longs(
            market_regime=market_regime,
            sector_regime=sector_regime,
            market_permission_score=market_permission_score,
        )

        reason_codes = [
            self._market_reason_code(market_regime),
            self._sector_reason_code(sector_regime),
        ]
        breadth_reason = self._breadth_reason_code(regime_input.breadth)
        if breadth_reason is not None:
            reason_codes.append(breadth_reason)
        volatility_reasons = self._volatility_reason_codes(high_vol=high_vol, risk_off_vol=risk_off_vol)
        reason_codes.extend(volatility_reasons)
        if not coverage_complete:
            reason_codes.append("REGIME_PARTIAL_COVERAGE")

        known_at = max(
            index.latest_bar.known_at for index in indexes.values()
        )
        known_at = max(known_at, regime_input.sector.latest_bar.known_at, regime_input.stock_relative.latest_bar.known_at)
        if regime_input.breadth is not None:
            known_at = max(known_at, regime_input.breadth.known_at)
        if regime_input.volatility is not None:
            known_at = max(known_at, regime_input.volatility.known_at)

        return RegimeEngineResult(
            config_version=self.config.config_version,
            market_regime=market_regime,
            sector_regime=sector_regime,
            market_permission_score=market_permission_score,
            sector_permission_score=sector_permission_score,
            stock_structure_quality_score=regime_input.stock_relative.structure_quality_score,
            allows_longs=allows_longs,
            coverage_complete=coverage_complete,
            reason_codes=reason_codes,
            known_at=known_at,
            extensible_context={
                "market_component_scores": market_components,
                "sector_component_scores": {
                    "direction": sector_direction,
                    "rs_supportive": sector_rs_supportive,
                    "rs_hostile": sector_rs_hostile,
                    "momentum_supportive": momentum_supportive,
                    "momentum_hostile": momentum_hostile,
                },
                "stock_relative_snapshot": {
                    "ticker": regime_input.stock_relative.ticker,
                    "relative_strength_vs_spy": self._decimal_or_none(regime_input.stock_relative.relative_strength_vs_spy),
                    "relative_strength_vs_sector": self._decimal_or_none(regime_input.stock_relative.relative_strength_vs_sector),
                    "structure_quality_score": self._decimal_or_none(regime_input.stock_relative.structure_quality_score),
                },
                "breadth_snapshot": {
                    "advance_decline_ratio": self._decimal_or_none(regime_input.breadth.advance_decline_ratio)
                    if regime_input.breadth is not None
                    else None,
                    "up_volume_ratio": self._decimal_or_none(regime_input.breadth.up_volume_ratio)
                    if regime_input.breadth is not None
                    else None,
                },
                "volatility_snapshot": {
                    "realized_volatility_20d": self._decimal_or_none(regime_input.volatility.realized_volatility_20d)
                    if regime_input.volatility is not None
                    else None,
                    "realized_volatility_5d": self._decimal_or_none(regime_input.volatility.realized_volatility_5d)
                    if regime_input.volatility is not None
                    else None,
                },
            },
        )

    def _validate_input(self, regime_input: RegimeEngineInput) -> dict[str, RegimeIndexInput]:
        indexes = {index.ticker: index for index in regime_input.market_indexes}
        if set(indexes) != {"SPY", "QQQ", "IWM"}:
            raise ValueError("Regime engine requires exactly SPY, QQQ, and IWM inputs.")
        for ticker, index in indexes.items():
            if not index.structure_history:
                raise ValueError(f"{ticker} structure history cannot be empty.")
            if index.structure_history[-1].bar_timestamp != index.structure.bar_timestamp:
                raise ValueError(f"{ticker} latest structure must match structure_history[-1].")
        if not regime_input.sector.sector_etf_ticker:
            raise ValueError("Sector ETF input is required.")
        if not regime_input.sector.structure_history:
            raise ValueError("Sector structure history cannot be empty.")
        if regime_input.sector.structure_history[-1].bar_timestamp != regime_input.sector.structure.bar_timestamp:
            raise ValueError("Sector latest structure must match structure_history[-1].")
        return indexes

    def _index_directional_component(self, index: RegimeIndexInput) -> int:
        if (
            index.structure.trend_state == "BEARISH_SEQUENCE"
            or self._recent_has_bearish_event(index.structure_history)
        ):
            return -1
        if (
            index.structure.trend_state == "BULLISH_SEQUENCE"
            and index.zone.range_status == "RANGE_AVAILABLE"
        ):
            return 1
        return 0

    def _recent_has_bearish_event(self, structure_history) -> bool:
        recent = structure_history[-self.config.bearish_event_lookback_bars :]
        return any(
            event.event_type in {"BEARISH_BOS", "BEARISH_CHOCH"}
            for result in recent
            for event in result.events_on_bar
        )

    def _classify_market_regime(
        self,
        *,
        market_trend_score: int,
        breadth_weak: bool,
        high_vol: bool,
        risk_off_vol: bool,
    ) -> str:
        if market_trend_score <= -2 or (market_trend_score <= -1 and breadth_weak and risk_off_vol):
            return "RISK_OFF"
        if market_trend_score >= 2 and not risk_off_vol and not high_vol:
            return "BULLISH_TREND"
        if market_trend_score >= 1 and high_vol:
            return "HIGH_VOL_EXPANSION"
        if market_trend_score == 1 and not breadth_weak:
            return "WEAK_DRIFT"
        return "CHOP"

    def _sector_direction(self, sector: SectorRegimeInput) -> str:
        if (
            sector.structure.trend_state == "BEARISH_SEQUENCE"
            or self._recent_has_bearish_event(sector.structure_history)
        ):
            return "BEARISH"
        if (
            sector.structure.trend_state == "BULLISH_SEQUENCE"
            and sector.zone.range_status == "RANGE_AVAILABLE"
        ):
            return "BULLISH"
        return "NEUTRAL"

    def _classify_sector_regime(
        self,
        *,
        sector_direction: str,
        sector_rs_supportive: bool,
        sector_rs_hostile: bool,
        momentum_supportive: bool,
        momentum_hostile: bool,
    ) -> str:
        if sector_direction == "BEARISH":
            return "SECTOR_WEAK"
        if sector_rs_hostile and momentum_hostile:
            return "SECTOR_WEAK"
        if sector_direction == "BULLISH" and (sector_rs_supportive or momentum_supportive):
            return "SECTOR_STRONG"
        return "SECTOR_NEUTRAL"

    def _market_permission_score(
        self,
        *,
        market_trend_score: int,
        breadth_strong: bool,
        breadth_weak: bool,
        high_vol: bool,
        risk_off_vol: bool,
    ) -> Decimal:
        score = Decimal("0.50")
        if market_trend_score >= 2:
            score += Decimal("0.25")
        elif market_trend_score == 1:
            score += Decimal("0.10")
        if breadth_strong:
            score += Decimal("0.10")
        if breadth_weak:
            score -= Decimal("0.15")
        if high_vol:
            score -= Decimal("0.20")
        if risk_off_vol:
            score -= Decimal("0.35")
        if market_trend_score <= -2:
            score -= Decimal("0.25")
        elif market_trend_score == -1:
            score -= Decimal("0.10")
        return self._clamp(score)

    def _sector_permission_score(
        self,
        *,
        sector_direction: str,
        sector_rs_supportive: bool,
        sector_rs_hostile: bool,
        momentum_supportive: bool,
        momentum_hostile: bool,
    ) -> Decimal:
        score = Decimal("0.50")
        if sector_direction == "BULLISH":
            score += Decimal("0.20")
        if sector_rs_supportive:
            score += Decimal("0.15")
        if momentum_supportive:
            score += Decimal("0.10")
        if sector_direction == "BEARISH":
            score -= Decimal("0.20")
        if sector_rs_hostile:
            score -= Decimal("0.15")
        if momentum_hostile:
            score -= Decimal("0.10")
        return self._clamp(score)

    def _allows_longs(self, *, market_regime: str, sector_regime: str, market_permission_score: Decimal) -> bool:
        if market_regime == "RISK_OFF":
            return False
        if (
            sector_regime == "SECTOR_WEAK"
            and market_permission_score < self.config.weak_sector_market_permission_block_threshold
        ):
            return False
        return True

    def _market_reason_code(self, market_regime: str) -> str:
        return {
            "BULLISH_TREND": "MARKET_BULLISH_TREND",
            "CHOP": "MARKET_CHOP",
            "RISK_OFF": "MARKET_RISK_OFF",
            "HIGH_VOL_EXPANSION": "MARKET_HIGH_VOL_EXPANSION",
            "WEAK_DRIFT": "MARKET_WEAK_DRIFT",
        }[market_regime]

    def _sector_reason_code(self, sector_regime: str) -> str:
        return {
            "SECTOR_STRONG": "SECTOR_STRONG",
            "SECTOR_NEUTRAL": "SECTOR_NEUTRAL",
            "SECTOR_WEAK": "SECTOR_WEAK",
        }[sector_regime]

    def _breadth_reason_code(self, breadth: BreadthInput | None) -> str | None:
        if breadth is None or breadth.advance_decline_ratio is None:
            return None
        if breadth.advance_decline_ratio >= self.config.breadth_strong_threshold:
            return "BREADTH_STRONG"
        if breadth.advance_decline_ratio < self.config.breadth_weak_threshold:
            return "BREADTH_WEAK"
        return None

    def _volatility_reason_codes(self, *, high_vol: bool, risk_off_vol: bool) -> list[str]:
        reason_codes: list[str] = []
        if high_vol:
            reason_codes.append("HIGH_VOL")
        if risk_off_vol:
            reason_codes.append("RISK_OFF_VOL")
        return reason_codes

    def _breadth_complete(self, breadth: BreadthInput | None) -> bool:
        return breadth is not None and breadth.advance_decline_ratio is not None and breadth.up_volume_ratio is not None

    def _volatility_complete(self, volatility: VolatilityInput | None) -> bool:
        return (
            volatility is not None
            and volatility.realized_volatility_20d is not None
            and volatility.realized_volatility_5d is not None
        )

    def _breadth_strong(self, breadth: BreadthInput | None) -> bool:
        return breadth is not None and breadth.advance_decline_ratio is not None and breadth.advance_decline_ratio >= self.config.breadth_strong_threshold

    def _breadth_weak(self, breadth: BreadthInput | None) -> bool:
        return breadth is not None and breadth.advance_decline_ratio is not None and breadth.advance_decline_ratio < self.config.breadth_weak_threshold

    def _high_vol(self, volatility: VolatilityInput | None) -> bool:
        if not self._volatility_complete(volatility):
            return False
        assert volatility is not None
        return volatility.realized_volatility_5d >= self.config.high_vol_ratio * volatility.realized_volatility_20d

    def _risk_off_vol(self, volatility: VolatilityInput | None) -> bool:
        if not self._volatility_complete(volatility):
            return False
        assert volatility is not None
        return volatility.realized_volatility_5d >= self.config.risk_off_vol_ratio * volatility.realized_volatility_20d

    def _sector_rs_supportive(self, sector: SectorRegimeInput) -> bool:
        return (
            sector.relative_strength_vs_spy is not None
            and sector.relative_strength_vs_spy >= self.config.sector_rs_strong_threshold
        )

    def _sector_rs_hostile(self, sector: SectorRegimeInput) -> bool:
        return (
            sector.relative_strength_vs_spy is not None
            and sector.relative_strength_vs_spy <= self.config.sector_rs_weak_threshold
        )

    def _momentum_supportive(self, sector: SectorRegimeInput) -> bool:
        return (
            sector.momentum_persistence_score is not None
            and sector.momentum_persistence_score >= self.config.momentum_supportive_threshold
        )

    def _momentum_hostile(self, sector: SectorRegimeInput) -> bool:
        return (
            sector.momentum_persistence_score is not None
            and sector.momentum_persistence_score < self.config.momentum_hostile_threshold
        )

    def _clamp(self, value: Decimal) -> Decimal:
        return max(Decimal("0.0000"), min(Decimal("1.0000"), value.quantize(Decimal("0.0000"))))

    def _decimal_or_none(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None
