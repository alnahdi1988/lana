from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.event_risk.models import EventRiskEngineResult
from doctrine_engine.ranking.engine import RankingEngine
from doctrine_engine.ranking.models import RankingEngineInput
from doctrine_engine.regime.models import RegimeEngineResult


def _signal_result(
    *,
    signal: str = "LONG",
    grade: str = "A",
    confidence: str = "0.80",
    setup_state: str = "RECONTAINMENT_CONFIRMED",
) -> SignalEngineResult:
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
        signal=signal,
        signal_version="v1",
        confidence=Decimal(confidence),
        grade=grade,
        bias_htf="BULLISH",
        setup_state=setup_state,
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={},
    )


def _trade_plan_result(signal_result: SignalEngineResult, *, entry_type: str = "BASE") -> TradePlanEngineResult:
    return TradePlanEngineResult(
        signal_id=uuid.uuid4(),
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
        entry_type=entry_type,
        entry_zone_low=Decimal("10.00"),
        entry_zone_high=Decimal("10.50"),
        confirmation_level=Decimal("10.60"),
        invalidation_level=Decimal("10.00"),
        tp1=Decimal("11.80"),
        tp2=Decimal("12.80"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )


def _regime_result(*, market_regime: str = "BULLISH_TREND", sector_regime: str = "SECTOR_STRONG") -> RegimeEngineResult:
    return RegimeEngineResult(
        config_version="v1",
        market_regime=market_regime,
        sector_regime=sector_regime,
        market_permission_score=Decimal("0.80"),
        sector_permission_score=Decimal("0.70"),
        stock_structure_quality_score=Decimal("0.88"),
        allows_longs=True,
        coverage_complete=True,
        reason_codes=["MARKET_BULLISH_TREND", "SECTOR_STRONG"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _event_risk_result(*, blocked: bool = False) -> EventRiskEngineResult:
    return EventRiskEngineResult(
        config_version="v1",
        event_risk_class="NO_EVENT_RISK" if not blocked else "EARNINGS_BLOCK",
        blocked=blocked,
        coverage_complete=True,
        soft_penalty=Decimal("0.0000"),
        reason_codes=["EVENT_RISK_CLEAR"] if not blocked else ["EARNINGS_BLACKOUT_ACTIVE"],
        known_at=datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _ranking_input(
    *,
    signal: str = "LONG",
    grade: str = "A",
    confidence: str = "0.80",
    setup_state: str = "RECONTAINMENT_CONFIRMED",
    entry_type: str = "BASE",
) -> RankingEngineInput:
    signal_result = _signal_result(signal=signal, grade=grade, confidence=confidence, setup_state=setup_state)
    trade_plan_result = _trade_plan_result(signal_result, entry_type=entry_type)
    return RankingEngineInput(
        signal_id=trade_plan_result.signal_id,
        signal_result=signal_result,
        trade_plan_result=trade_plan_result,
        regime_result=_regime_result(),
        event_risk_result=_event_risk_result(),
    )


def test_a_plus_ranks_above_a_with_same_inputs() -> None:
    engine = RankingEngine()
    a_plus = engine.evaluate(_ranking_input(grade="A+"))
    a_only = engine.evaluate(_ranking_input(grade="A"))
    assert a_plus.baseline_score > a_only.baseline_score


def test_confidence_materially_affects_score() -> None:
    engine = RankingEngine()
    high = engine.evaluate(_ranking_input(confidence="0.90"))
    low = engine.evaluate(_ranking_input(confidence="0.60"))
    assert high.baseline_score > low.baseline_score


def test_setup_state_weights_are_deterministic() -> None:
    engine = RankingEngine()
    recontainment = engine.evaluate(_ranking_input(setup_state="RECONTAINMENT_CONFIRMED"))
    equilibrium = engine.evaluate(_ranking_input(setup_state="EQUILIBRIUM_HOLD"))
    assert recontainment.baseline_score > equilibrium.baseline_score


def test_entry_type_weights_are_deterministic() -> None:
    engine = RankingEngine()
    confirmation = engine.evaluate(_ranking_input(entry_type="CONFIRMATION"))
    aggressive = engine.evaluate(_ranking_input(entry_type="AGGRESSIVE"))
    assert confirmation.baseline_score > aggressive.baseline_score


def test_b_signal_may_still_be_ranked() -> None:
    result = RankingEngine().evaluate(_ranking_input(grade="B"))
    assert result.ranking_state == "RANKED"


def test_non_long_forces_skipped_not_long_mapping() -> None:
    result = RankingEngine().evaluate(_ranking_input(signal="NONE"))
    assert result.ranking_state == "SKIPPED_NOT_LONG"
    assert result.final_score == Decimal("0.0000")
    assert result.ranking_tier == "DO_NOT_QUEUE"
    assert result.ranking_grade == "R0"
    assert result.ranking_label == "BLOCKED_NON_LONG"
    assert result.reason_codes == ["RANK_NON_LONG", "RANK_TIER_DO_NOT_QUEUE"]
