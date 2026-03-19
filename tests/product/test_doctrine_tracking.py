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
        self.signals: dict[uuid.UUID, Signal] = {}
        self.trade_plans: dict[uuid.UUID, TradePlan] = {}
        self.outcomes: dict[uuid.UUID, Outcome] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, key):
        if model is Signal:
            return self.signals.get(key)
        if model is TradePlan:
            return self.trade_plans.get(key)
        if model is Outcome:
            return self.outcomes.get(key)
        return None

    def scalar(self, statement):
        if self.scalars_rows:
            return self.scalars_rows.pop(0)
        entity = statement.column_descriptions[0]["entity"]
        criteria = {}
        for clause in statement._where_criteria:
            children = list(clause.get_children())
            if len(children) == 2 and hasattr(children[0], "key"):
                criteria[children[0].key] = children[1].value
        if entity is Signal:
            for signal in self.signals.values():
                if all(getattr(signal, key) == value for key, value in criteria.items()):
                    return signal
            return None
        if entity is TradePlan:
            for trade_plan in self.trade_plans.values():
                if all(getattr(trade_plan, key) == value for key, value in criteria.items()):
                    return trade_plan
            return None
        if entity is Outcome:
            for outcome in self.outcomes.values():
                if all(getattr(outcome, key) == value for key, value in criteria.items()):
                    return outcome
            return None
        return None

    def add(self, value):
        self.added.append(value)
        if isinstance(value, Signal):
            self.signals[value.id] = value
        elif isinstance(value, TradePlan):
            self.trade_plans[value.signal_id] = value
        elif isinstance(value, Outcome):
            self.outcomes[value.signal_id] = value

    def commit(self):
        return None

    def scalars(self, statement):
        return iter(self.scalars_rows)

    def begin_nested(self):
        class _Nested:
            def __enter__(self_inner):
                return self

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Nested()

    def flush(self):
        return None


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


def test_doctrine_lifecycle_store_is_idempotent_for_symbol_and_timestamp():
    fake_session = _FakeSession()
    store = DoctrineLifecycleStore(session_factory=lambda: fake_session, time_barrier_bars=20)
    setup = _qualifying_setup_record()
    duplicate_setup = QualifyingSetupRecord(
        run_id=uuid.uuid4(),
        signal_id=uuid.uuid4(),
        signal_result=setup.signal_result,
        trade_plan_result=TradePlanEngineResult(
            signal_id=uuid.uuid4(),
            symbol_id=setup.trade_plan_result.symbol_id,
            ticker=setup.trade_plan_result.ticker,
            plan_timestamp=setup.trade_plan_result.plan_timestamp,
            known_at=setup.trade_plan_result.known_at,
            entry_type=setup.trade_plan_result.entry_type,
            entry_zone_low=setup.trade_plan_result.entry_zone_low,
            entry_zone_high=setup.trade_plan_result.entry_zone_high,
            confirmation_level=setup.trade_plan_result.confirmation_level,
            invalidation_level=setup.trade_plan_result.invalidation_level,
            tp1=setup.trade_plan_result.tp1,
            tp2=setup.trade_plan_result.tp2,
            trail_mode=setup.trade_plan_result.trail_mode,
            plan_reason_codes=list(setup.trade_plan_result.plan_reason_codes),
            extensible_context=dict(setup.trade_plan_result.extensible_context),
        ),
        decision_result=setup.decision_result,
    )

    first = store.record_qualifying_setups([setup])
    second = store.record_qualifying_setups([duplicate_setup])

    assert first.recorded_signals == 1
    assert first.recorded_trade_plans == 1
    assert first.initialized_outcomes == 1
    assert second.recorded_signals == 0
    assert second.recorded_trade_plans == 0
    assert second.initialized_outcomes == 0
    assert second.skipped_existing == 1
    assert len(fake_session.signals) == 1
    assert len(fake_session.trade_plans) == 1
    assert len(fake_session.outcomes) == 1


def test_doctrine_lifecycle_store_backfills_missing_outcome_for_existing_signal():
    fake_session = _FakeSession()
    store = DoctrineLifecycleStore(session_factory=lambda: fake_session, time_barrier_bars=20)
    setup = _qualifying_setup_record()
    existing_signal = Signal(
        id=uuid.uuid4(),
        symbol_id=setup.signal_result.symbol_id,
        universe_snapshot_id=setup.signal_result.universe_snapshot_id,
        signal_timestamp=setup.signal_result.signal_timestamp,
        known_at=setup.signal_result.known_at,
        htf_bar_timestamp=setup.signal_result.htf_bar_timestamp,
        mtf_bar_timestamp=setup.signal_result.mtf_bar_timestamp,
        ltf_bar_timestamp=setup.signal_result.ltf_bar_timestamp,
        signal="LONG",
        signal_version=setup.signal_result.signal_version,
        confidence=setup.signal_result.confidence,
        grade=setup.signal_result.grade,
        bias_htf=setup.signal_result.bias_htf,
        setup_state=setup.signal_result.setup_state,
        reason_codes=list(setup.signal_result.reason_codes),
        event_risk_blocked=setup.signal_result.event_risk_blocked,
        extensible_context={},
    )
    existing_trade_plan = TradePlan(
        signal_id=existing_signal.id,
        plan_timestamp=setup.trade_plan_result.plan_timestamp,
        known_at=setup.trade_plan_result.known_at,
        entry_type=setup.trade_plan_result.entry_type,
        entry_zone_low=setup.trade_plan_result.entry_zone_low,
        entry_zone_high=setup.trade_plan_result.entry_zone_high,
        confirmation_level=setup.trade_plan_result.confirmation_level,
        invalidation_level=setup.trade_plan_result.invalidation_level,
        tp1=setup.trade_plan_result.tp1,
        tp2=setup.trade_plan_result.tp2,
        trail_mode=setup.trade_plan_result.trail_mode,
        plan_reason_codes=list(setup.trade_plan_result.plan_reason_codes),
        extensible_context={},
    )
    fake_session.signals[existing_signal.id] = existing_signal
    fake_session.trade_plans[existing_signal.id] = existing_trade_plan

    summary = store.record_qualifying_setups([setup])

    assert summary.recorded_signals == 0
    assert summary.recorded_trade_plans == 0
    assert summary.initialized_outcomes == 1
    assert summary.skipped_existing == 1
    assert existing_signal.id in fake_session.outcomes
    assert existing_signal.extensible_context["market_regime"] == "BULLISH_TREND"
    assert existing_signal.extensible_context["alert_state"] == setup.decision_result.alert_state
    assert existing_signal.reason_codes == ["PRICE_RANGE_VALID"]


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
