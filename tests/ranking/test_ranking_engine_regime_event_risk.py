from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.event_risk.models import EventRiskEngineResult
from doctrine_engine.ranking.engine import RankingEngine
from doctrine_engine.ranking.models import RankingEngineInput
from doctrine_engine.regime.models import RegimeEngineResult


def _signal_result() -> SignalEngineResult:
    symbol_id = uuid.uuid4()
    signal_timestamp = datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc)
    known_at = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    return SignalEngineResult(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        signal_timestamp=signal_timestamp,
        known_at=known_at,
        htf_bar_timestamp=signal_timestamp,
        mtf_bar_timestamp=signal_timestamp,
        ltf_bar_timestamp=signal_timestamp,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.70"),
        grade="A",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={},
    )


def _trade_plan_result(signal_result: SignalEngineResult) -> TradePlanEngineResult:
    return TradePlanEngineResult(
        signal_id=uuid.uuid4(),
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
        entry_type="BASE",
        entry_zone_low=Decimal("10.00"),
        entry_zone_high=Decimal("10.50"),
        confirmation_level=Decimal("10.60"),
        invalidation_level=Decimal("10.00"),
        tp1=Decimal("11.40"),
        tp2=Decimal("12.00"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def _regime_result(
    *,
    market_regime: str = "BULLISH_TREND",
    sector_regime: str = "SECTOR_STRONG",
    coverage_complete: bool = True,
) -> RegimeEngineResult:
    return RegimeEngineResult(
        config_version="v1",
        market_regime=market_regime,
        sector_regime=sector_regime,
        market_permission_score=Decimal("0.30"),
        sector_permission_score=Decimal("0.20"),
        stock_structure_quality_score=Decimal("0.88"),
        allows_longs=True,
        coverage_complete=coverage_complete,
        reason_codes=["MARKET_BULLISH_TREND", "SECTOR_STRONG"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _event_risk_result(
    *,
    blocked: bool = False,
    coverage_complete: bool = True,
    soft_penalty: str = "0.0000",
) -> EventRiskEngineResult:
    return EventRiskEngineResult(
        config_version="v1",
        event_risk_class="EARNINGS_BLOCK" if blocked else "NO_EVENT_RISK",
        blocked=blocked,
        coverage_complete=coverage_complete,
        soft_penalty=Decimal(soft_penalty),
        reason_codes=["EARNINGS_BLACKOUT_ACTIVE"] if blocked else ["EVENT_RISK_CLEAR"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _ranking_input(
    *,
    market_regime: str = "BULLISH_TREND",
    sector_regime: str = "SECTOR_STRONG",
    regime_coverage_complete: bool = True,
    event_blocked: bool = False,
    event_coverage_complete: bool = True,
    soft_penalty: str = "0.0000",
) -> RankingEngineInput:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    return RankingEngineInput(
        signal_id=trade_plan_result.signal_id,
        signal_result=signal_result,
        trade_plan_result=trade_plan_result,
        regime_result=_regime_result(
            market_regime=market_regime,
            sector_regime=sector_regime,
            coverage_complete=regime_coverage_complete,
        ),
        event_risk_result=_event_risk_result(
            blocked=event_blocked,
            coverage_complete=event_coverage_complete,
            soft_penalty=soft_penalty,
        ),
    )


def test_event_risk_blocked_overrides_strong_inputs_and_forces_skip() -> None:
    result = RankingEngine().evaluate(_ranking_input(event_blocked=True))
    assert result.ranking_state == "SKIPPED_BLOCKED"
    assert result.final_score == Decimal("0.0000")
    assert result.ranking_tier == "DO_NOT_QUEUE"
    assert result.ranking_grade == "R0"
    assert result.ranking_label == "BLOCKED_EVENT_RISK"
    assert result.reason_codes == ["RANK_EVENT_BLOCKED", "RANK_TIER_DO_NOT_QUEUE"]


def test_bullish_trend_improves_score() -> None:
    engine = RankingEngine()
    bullish = engine.evaluate(_ranking_input(market_regime="BULLISH_TREND"))
    chop = engine.evaluate(_ranking_input(market_regime="CHOP"))
    assert bullish.final_score > chop.final_score


def test_weak_drift_mildly_improves_score() -> None:
    engine = RankingEngine()
    weak_drift = engine.evaluate(_ranking_input(market_regime="WEAK_DRIFT"))
    chop = engine.evaluate(_ranking_input(market_regime="CHOP"))
    assert weak_drift.final_score > chop.final_score


def test_high_vol_expansion_penalizes_score() -> None:
    engine = RankingEngine()
    bullish = engine.evaluate(_ranking_input(market_regime="BULLISH_TREND"))
    high_vol = engine.evaluate(_ranking_input(market_regime="HIGH_VOL_EXPANSION"))
    assert bullish.final_score > high_vol.final_score


def test_sector_strong_helps_and_sector_weak_hurts() -> None:
    engine = RankingEngine()
    strong = engine.evaluate(_ranking_input(sector_regime="SECTOR_STRONG"))
    weak = engine.evaluate(_ranking_input(sector_regime="SECTOR_WEAK"))
    assert strong.final_score > weak.final_score


def test_partial_coverage_penalty_is_applied() -> None:
    full = RankingEngine().evaluate(_ranking_input())
    partial = RankingEngine().evaluate(
        _ranking_input(regime_coverage_complete=False, event_coverage_complete=False)
    )
    assert partial.final_score < full.final_score
    assert "RANK_PARTIAL_COVERAGE_PENALTY" in partial.reason_codes
