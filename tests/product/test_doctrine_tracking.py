from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.alerts.workflow import AlertWorkflow
from doctrine_engine.db.models.market_data import Bar
from doctrine_engine.db.models.signals import Outcome, Signal, TradePlan
from doctrine_engine.db.types import EvaluationStatus
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult
from doctrine_engine.product.doctrine_tracking import DoctrineLifecycleStore, QualifyingSetupRecord


class _FakeSession:
    def __init__(self, *, scalars_rows=None):
        self.scalars_rows = list(scalars_rows or [])
        self.added: list[object] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, key):
        return None

    def scalar(self, statement):
        return None

    def add(self, value):
        self.added.append(value)

    def commit(self):
        return None

    def scalars(self, statement):
        return iter(self.scalars_rows)


def _qualifying_setup_record() -> QualifyingSetupRecord:
    known_at = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    signal_id = uuid.uuid4()
    symbol_id = uuid.uuid4()
    signal_result = SignalEngineResult(
        symbol_id=symbol_id,
        ticker="TEST",
        universe_snapshot_id=None,
        signal_timestamp=known_at,
        known_at=known_at,
        htf_bar_timestamp=known_at,
        mtf_bar_timestamp=known_at,
        ltf_bar_timestamp=known_at,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.7400"),
        grade="B",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={
            "market_regime": "BULLISH_TREND",
            "sector_regime": "SECTOR_STRONG",
            "event_risk_class": "NO_EVENT_RISK",
            "micro_state": "AVAILABLE_NOT_USED",
            "micro_present": True,
            "micro_trigger_state": "LTF_BULLISH_RECLAIM",
            "micro_used_for_confirmation": False,
        },
    )
    trade_plan_result = TradePlanEngineResult(
        signal_id=signal_id,
        symbol_id=symbol_id,
        ticker="TEST",
        plan_timestamp=known_at,
        known_at=known_at,
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5000"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("11.2000"),
        tp2=Decimal("12.0000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )
    decision_result = AlertWorkflow().evaluate(
        AlertWorkflowInput(
            signal_id=signal_id,
            signal_result=signal_result,
            trade_plan_result=trade_plan_result,
            prior_alert_state=None,
            snapshot_request_config=None,
        )
    )
    return QualifyingSetupRecord(
        run_id=uuid.uuid4(),
        signal_id=signal_id,
        signal_result=signal_result,
        trade_plan_result=trade_plan_result,
        decision_result=decision_result,
    )


def test_doctrine_lifecycle_store_records_suppressed_qualifying_setup():
    fake_session = _FakeSession()
    store = DoctrineLifecycleStore(session_factory=lambda: fake_session, time_barrier_bars=20)

    summary = store.record_qualifying_setups([_qualifying_setup_record()])

    assert summary.recorded_signals == 1
    assert summary.recorded_trade_plans == 1
    assert summary.initialized_outcomes == 1
    assert any(isinstance(item, Signal) for item in fake_session.added)
    assert any(isinstance(item, TradePlan) for item in fake_session.added)
    assert any(isinstance(item, Outcome) for item in fake_session.added)


def test_doctrine_lifecycle_store_updates_outcome_labels_from_delayed_bars():
    known_at = datetime(2026, 3, 11, 10, 15, tzinfo=timezone.utc)
    signal = Signal(
        id=uuid.uuid4(),
        symbol_id=uuid.uuid4(),
        universe_snapshot_id=None,
        signal_timestamp=known_at,
        known_at=known_at,
        htf_bar_timestamp=known_at,
        mtf_bar_timestamp=known_at,
        ltf_bar_timestamp=known_at,
        signal="LONG",
        signal_version="v1",
        confidence=Decimal("0.8100"),
        grade="A",
        bias_htf="BULLISH",
        setup_state="RECONTAINMENT_CONFIRMED",
        reason_codes=["PRICE_RANGE_VALID"],
        event_risk_blocked=False,
        extensible_context={},
    )
    trade_plan = TradePlan(
        signal_id=signal.id,
        plan_timestamp=known_at,
        known_at=known_at,
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5000"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("11.2000"),
        tp2=Decimal("12.0000"),
        trail_mode="STRUCTURAL",
        plan_reason_codes=["ENTRY_FROM_RECONTAINMENT"],
        extensible_context={},
    )
    outcome = Outcome(signal_id=signal.id, evaluation_status=EvaluationStatus.PENDING, bars_tracked=0, extensible_context={})
    fake_session = _FakeSession(
        scalars_rows=[
            Bar(
                symbol_id=signal.symbol_id,
                timeframe="15M",
                bar_timestamp=datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc),
                known_at=datetime(2026, 3, 11, 10, 45, tzinfo=timezone.utc),
                open_price=Decimal("10.2000"),
                high_price=Decimal("11.2500"),
                low_price=Decimal("10.0500"),
                close_price=Decimal("11.0000"),
                volume=1000,
            )
        ]
    )
    store = DoctrineLifecycleStore(session_factory=lambda: fake_session, time_barrier_bars=20)

    updated = store._update_one_outcome(fake_session, outcome, signal, trade_plan)

    assert updated == 1
    assert outcome.evaluation_status == EvaluationStatus.FINALIZED
    assert outcome.first_barrier == "TP1"
    assert outcome.success_label is True
    assert outcome.tp2_label is False
    assert outcome.invalidated_first is False
    assert outcome.bars_to_tp1 == 1
    assert outcome.bars_tracked == 1
    assert outcome.mfe_pct == Decimal("9.7561")
    assert outcome.mae_pct == Decimal("1.9512")
