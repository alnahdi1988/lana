from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

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


def _trade_plan_result(signal_result: SignalEngineResult, **overrides) -> TradePlanEngineResult:
    base = TradePlanEngineResult(
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
    return replace(base, **overrides)


def _regime_result(*, known_at: datetime | None = None) -> RegimeEngineResult:
    return RegimeEngineResult(
        config_version="v1",
        market_regime="BULLISH_TREND",
        sector_regime="SECTOR_STRONG",
        market_permission_score=Decimal("0.30"),
        sector_permission_score=Decimal("0.20"),
        stock_structure_quality_score=Decimal("0.88"),
        allows_longs=True,
        coverage_complete=True,
        reason_codes=["MARKET_BULLISH_TREND", "SECTOR_STRONG"],
        known_at=known_at or datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _event_risk_result(*, known_at: datetime | None = None) -> EventRiskEngineResult:
    return EventRiskEngineResult(
        config_version="v1",
        event_risk_class="NO_EVENT_RISK",
        blocked=False,
        coverage_complete=True,
        soft_penalty=Decimal("0.0000"),
        reason_codes=["EVENT_RISK_CLEAR"],
        known_at=known_at or datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc),
        extensible_context={},
    )


def _ranking_input(trade_plan_result: TradePlanEngineResult) -> RankingEngineInput:
    signal_result = _signal_result()
    trade_plan_result = replace(
        trade_plan_result,
        signal_id=trade_plan_result.signal_id,
        symbol_id=signal_result.symbol_id,
        ticker=signal_result.ticker,
        plan_timestamp=signal_result.signal_timestamp,
        known_at=signal_result.known_at,
    )
    return RankingEngineInput(
        signal_id=trade_plan_result.signal_id,
        signal_result=signal_result,
        trade_plan_result=trade_plan_result,
        regime_result=_regime_result(),
        event_risk_result=_event_risk_result(),
    )


def test_strong_rr1_and_rr2_improve_score() -> None:
    signal_result = _signal_result()
    strong = RankingEngine().evaluate(
        _ranking_input(
            _trade_plan_result(signal_result, tp1=Decimal("11.90"), tp2=Decimal("13.20"))
        )
    )
    weak = RankingEngine().evaluate(
        _ranking_input(
            _trade_plan_result(signal_result, tp1=Decimal("11.10"), tp2=Decimal("11.90"))
        )
    )
    assert strong.final_score > weak.final_score
    assert "RANK_RR1_STRONG" in strong.reason_codes
    assert "RANK_RR2_STRONG" in strong.reason_codes


def test_weak_rr1_penalizes_score() -> None:
    signal_result = _signal_result()
    weak = RankingEngine().evaluate(
        _ranking_input(
            _trade_plan_result(signal_result, tp1=Decimal("11.10"), tp2=Decimal("11.90"))
        )
    )
    assert "RANK_RR1_WEAK" in weak.reason_codes


def test_confirmation_entry_adds_score_and_aggressive_penalizes() -> None:
    signal_result = _signal_result()
    confirmation = RankingEngine().evaluate(
        _ranking_input(_trade_plan_result(signal_result, entry_type="CONFIRMATION"))
    )
    aggressive = RankingEngine().evaluate(
        _ranking_input(_trade_plan_result(signal_result, entry_type="AGGRESSIVE"))
    )
    assert confirmation.final_score > aggressive.final_score
    assert "RANK_CONFIRMATION_ENTRY" in confirmation.reason_codes
    assert "RANK_AGGRESSIVE_ENTRY" in aggressive.reason_codes


def test_risk_distance_below_floor_raises() -> None:
    signal_result = _signal_result()
    with pytest.raises(ValueError):
        RankingEngine().evaluate(
            _ranking_input(
                _trade_plan_result(
                    signal_result,
                    confirmation_level=Decimal("10.60"),
                    invalidation_level=Decimal("10.58"),
                )
            )
        )


def test_invalid_target_ordering_raises() -> None:
    signal_result = _signal_result()
    with pytest.raises(ValueError):
        RankingEngine().evaluate(
            _ranking_input(
                _trade_plan_result(signal_result, tp1=Decimal("10.50"), tp2=Decimal("10.70"))
            )
        )


def test_known_at_violations_raise() -> None:
    signal_result = _signal_result()
    trade_plan_result = _trade_plan_result(signal_result)
    with pytest.raises(ValueError):
        RankingEngine().evaluate(
            RankingEngineInput(
                signal_id=trade_plan_result.signal_id,
                signal_result=signal_result,
                trade_plan_result=trade_plan_result,
                regime_result=_regime_result(
                    known_at=datetime(2026, 3, 11, 10, 20, tzinfo=timezone.utc)
                ),
                event_risk_result=_event_risk_result(),
            )
        )
