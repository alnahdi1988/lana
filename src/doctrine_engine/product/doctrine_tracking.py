from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.alerts.models import AlertDecisionResult
from doctrine_engine.db.models.market_data import Bar
from doctrine_engine.db.models.signals import Outcome, Signal, TradePlan
from doctrine_engine.db.models.symbols import Symbol
from doctrine_engine.db.types import EntryType, EvaluationStatus, HTFBias, SignalGrade, SignalValue, Timeframe, TrailMode
from doctrine_engine.engines.models import SignalEngineResult, TradePlanEngineResult


OUTCOME_TRACKING_TIMEFRAME = Timeframe.MIN_15
ENTRY_REFERENCE_MODE = "ENTRY_ZONE_MIDPOINT"


@dataclass(frozen=True, slots=True)
class QualifyingSetupRecord:
    run_id: uuid.UUID
    signal_id: uuid.UUID
    signal_result: SignalEngineResult
    trade_plan_result: TradePlanEngineResult
    decision_result: AlertDecisionResult


@dataclass(frozen=True, slots=True)
class DoctrinePersistenceSummary:
    recorded_signals: int
    recorded_trade_plans: int
    initialized_outcomes: int
    skipped_existing: int


@dataclass(frozen=True, slots=True)
class OutcomeTrackingSummary:
    open_trades: int
    finalized_trades: int
    updated_outcomes: int
    latest_known_at: str | None
    latest_tracked_until: str | None
    tracking_timeframe: str
    time_barrier_bars: int


class DoctrineLifecycleStore:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        time_barrier_bars: int,
        tracking_timeframe: Timeframe = OUTCOME_TRACKING_TIMEFRAME,
    ) -> None:
        self.session_factory = session_factory
        self.time_barrier_bars = time_barrier_bars
        self.tracking_timeframe = tracking_timeframe

    def record_qualifying_setups(self, setups: Iterable[QualifyingSetupRecord]) -> DoctrinePersistenceSummary:
        recorded_signals = 0
        recorded_trade_plans = 0
        initialized_outcomes = 0
        skipped_existing = 0
        with self.session_factory() as session:
            for setup in setups:
                if setup.signal_result.signal != "LONG":
                    continue
                signal = session.get(Signal, setup.signal_id)
                if signal is None:
                    signal = Signal(
                        id=setup.signal_id,
                        symbol_id=setup.signal_result.symbol_id,
                        universe_snapshot_id=setup.signal_result.universe_snapshot_id,
                        signal_timestamp=setup.signal_result.signal_timestamp,
                        known_at=setup.signal_result.known_at,
                        htf_bar_timestamp=setup.signal_result.htf_bar_timestamp,
                        mtf_bar_timestamp=setup.signal_result.mtf_bar_timestamp,
                        ltf_bar_timestamp=setup.signal_result.ltf_bar_timestamp,
                        signal=SignalValue(setup.signal_result.signal),
                        signal_version=setup.signal_result.signal_version,
                        confidence=setup.signal_result.confidence,
                        grade=SignalGrade(setup.signal_result.grade),
                        bias_htf=HTFBias(setup.signal_result.bias_htf),
                        setup_state=setup.signal_result.setup_state,
                        reason_codes=list(setup.signal_result.reason_codes),
                        event_risk_blocked=setup.signal_result.event_risk_blocked,
                        extensible_context={
                            **dict(setup.signal_result.extensible_context),
                            "run_id": str(setup.run_id),
                            "alert_state": setup.decision_result.alert_state,
                            "suppression_reason": setup.decision_result.suppression_reason,
                            "telegram_sendable": setup.decision_result.send,
                        },
                    )
                    session.add(signal)
                    recorded_signals += 1
                else:
                    skipped_existing += 1

                existing_plan = session.scalar(select(TradePlan).where(TradePlan.signal_id == setup.signal_id))
                if existing_plan is None:
                    session.add(
                        TradePlan(
                            signal_id=setup.signal_id,
                            plan_timestamp=setup.trade_plan_result.plan_timestamp,
                            known_at=setup.trade_plan_result.known_at,
                            entry_type=EntryType(setup.trade_plan_result.entry_type),
                            entry_zone_low=setup.trade_plan_result.entry_zone_low,
                            entry_zone_high=setup.trade_plan_result.entry_zone_high,
                            confirmation_level=setup.trade_plan_result.confirmation_level,
                            invalidation_level=setup.trade_plan_result.invalidation_level,
                            tp1=setup.trade_plan_result.tp1,
                            tp2=setup.trade_plan_result.tp2,
                            trail_mode=TrailMode(setup.trade_plan_result.trail_mode),
                            plan_reason_codes=list(setup.trade_plan_result.plan_reason_codes),
                            extensible_context={
                                **dict(setup.trade_plan_result.extensible_context),
                                "operator_summary": setup.decision_result.payload.operator_summary,
                                "alert_state": setup.decision_result.alert_state,
                                "payload_fingerprint": setup.decision_result.payload_fingerprint,
                            },
                        )
                    )
                    recorded_trade_plans += 1

                existing_outcome = session.scalar(select(Outcome).where(Outcome.signal_id == setup.signal_id))
                if existing_outcome is None:
                    session.add(
                        Outcome(
                            signal_id=setup.signal_id,
                            evaluation_status=EvaluationStatus.PENDING,
                            evaluation_start=setup.trade_plan_result.plan_timestamp,
                            extensible_context={
                                "tracking_timeframe": self.tracking_timeframe.value,
                                "time_barrier_bars": self.time_barrier_bars,
                                "entry_reference_mode": ENTRY_REFERENCE_MODE,
                            },
                        )
                    )
                    initialized_outcomes += 1
            session.commit()
        return DoctrinePersistenceSummary(
            recorded_signals=recorded_signals,
            recorded_trade_plans=recorded_trade_plans,
            initialized_outcomes=initialized_outcomes,
            skipped_existing=skipped_existing,
        )

    def update_pending_outcomes(self) -> OutcomeTrackingSummary:
        updated_outcomes = 0
        with self.session_factory() as session:
            rows = session.execute(
                select(Outcome, Signal, TradePlan, Symbol.ticker)
                .join(Signal, Signal.id == Outcome.signal_id)
                .join(TradePlan, TradePlan.signal_id == Signal.id)
                .join(Symbol, Symbol.id == Signal.symbol_id)
                .where(Outcome.evaluation_status.in_([EvaluationStatus.PENDING, EvaluationStatus.EVALUATING]))
                .order_by(Signal.known_at.asc())
            ).all()
            for outcome, signal, trade_plan, _ticker in rows:
                updated_outcomes += self._update_one_outcome(session, outcome, signal, trade_plan)
            session.commit()
            latest_known_at = session.scalar(select(func.max(Signal.known_at)))
            latest_tracked_until = session.scalar(select(func.max(Outcome.tracked_until)))
            open_trades = session.scalar(
                select(func.count()).select_from(Outcome).where(Outcome.evaluation_status != EvaluationStatus.FINALIZED)
            )
            finalized_trades = session.scalar(
                select(func.count()).select_from(Outcome).where(Outcome.evaluation_status == EvaluationStatus.FINALIZED)
            )
        return OutcomeTrackingSummary(
            open_trades=int(open_trades or 0),
            finalized_trades=int(finalized_trades or 0),
            updated_outcomes=updated_outcomes,
            latest_known_at=latest_known_at.isoformat() if latest_known_at is not None else None,
            latest_tracked_until=latest_tracked_until.isoformat() if latest_tracked_until is not None else None,
            tracking_timeframe=self.tracking_timeframe.value,
            time_barrier_bars=self.time_barrier_bars,
        )

    def recent_trades(
        self,
        *,
        limit: int = 100,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        outcome_status: str | None = None,
    ) -> list[dict]:
        with self.session_factory() as session:
            statement = (
                select(Signal, TradePlan, Outcome, Symbol.ticker)
                .join(TradePlan, TradePlan.signal_id == Signal.id)
                .join(Outcome, Outcome.signal_id == Signal.id)
                .join(Symbol, Symbol.id == Signal.symbol_id)
                .order_by(Signal.known_at.desc())
                .limit(limit)
            )
            if ticker:
                statement = statement.where(Symbol.ticker == ticker)
            if signal:
                statement = statement.where(Signal.signal == SignalValue(signal))
            if setup_state:
                statement = statement.where(Signal.setup_state == setup_state)
            if outcome_status:
                statement = statement.where(Outcome.evaluation_status == EvaluationStatus(outcome_status))
            rows = session.execute(statement).all()
        return [self._trade_row(signal_row, trade_plan, outcome, ticker_value) for signal_row, trade_plan, outcome, ticker_value in rows]

    def trade_rows_by_signal_ids(self, signal_ids: Iterable[str]) -> dict[str, dict]:
        ids = [uuid.UUID(str(value)) for value in signal_ids if value]
        if not ids:
            return {}
        with self.session_factory() as session:
            rows = session.execute(
                select(Signal, TradePlan, Outcome, Symbol.ticker)
                .join(TradePlan, TradePlan.signal_id == Signal.id)
                .join(Outcome, Outcome.signal_id == Signal.id)
                .join(Symbol, Symbol.id == Signal.symbol_id)
                .where(Signal.id.in_(ids))
            ).all()
        return {
            str(signal_row.id): self._trade_row(signal_row, trade_plan, outcome, ticker_value)
            for signal_row, trade_plan, outcome, ticker_value in rows
        }

    def status_snapshot(self) -> dict:
        with self.session_factory() as session:
            latest_known_at = session.scalar(select(func.max(Signal.known_at)))
            latest_tracked_until = session.scalar(select(func.max(Outcome.tracked_until)))
            open_trades = session.scalar(
                select(func.count()).select_from(Outcome).where(Outcome.evaluation_status != EvaluationStatus.FINALIZED)
            )
            closed_trades = session.scalar(
                select(func.count()).select_from(Outcome).where(Outcome.evaluation_status == EvaluationStatus.FINALIZED)
            )
            total_signals = session.scalar(select(func.count()).select_from(Signal))
            total_trade_plans = session.scalar(select(func.count()).select_from(TradePlan))
            total_outcomes = session.scalar(select(func.count()).select_from(Outcome))
        return {
            "status": "READY",
            "tracking_timeframe": self.tracking_timeframe.value,
            "time_barrier_bars": self.time_barrier_bars,
            "open_trades": int(open_trades or 0),
            "closed_trades": int(closed_trades or 0),
            "total_signals": int(total_signals or 0),
            "total_trade_plans": int(total_trade_plans or 0),
            "total_outcomes": int(total_outcomes or 0),
            "latest_known_at": latest_known_at.isoformat() if latest_known_at is not None else None,
            "latest_tracked_until": latest_tracked_until.isoformat() if latest_tracked_until is not None else None,
        }

    def _update_one_outcome(self, session: Session, outcome: Outcome, signal: Signal, trade_plan: TradePlan) -> int:
        starting_bars = int(outcome.bars_tracked or 0)
        remaining_bars = max(self.time_barrier_bars - starting_bars, 0)
        if remaining_bars == 0 and outcome.evaluation_status != EvaluationStatus.FINALIZED:
            outcome.evaluation_status = EvaluationStatus.FINALIZED
            outcome.first_barrier = outcome.first_barrier or "TIME"
            outcome.success_label = False if outcome.success_label is None else outcome.success_label
            outcome.tp2_label = False if outcome.tp2_label is None else outcome.tp2_label
            outcome.invalidated_first = False if outcome.invalidated_first is None else outcome.invalidated_first
            outcome.evaluation_end = outcome.tracked_until or trade_plan.plan_timestamp
            return 1

        bars = list(
            session.scalars(
                select(Bar)
                .where(
                    Bar.symbol_id == signal.symbol_id,
                    Bar.timeframe == self.tracking_timeframe,
                    Bar.bar_timestamp > (outcome.tracked_until or trade_plan.plan_timestamp),
                )
                .order_by(Bar.bar_timestamp.asc())
                .limit(remaining_bars)
            )
        )
        if not bars:
            return 0

        entry_reference = _entry_reference_price(trade_plan.entry_zone_low, trade_plan.entry_zone_high)
        mfe_pct = Decimal(str(outcome.mfe_pct)) if outcome.mfe_pct is not None else Decimal("0")
        mae_pct = Decimal(str(outcome.mae_pct)) if outcome.mae_pct is not None else Decimal("0")
        bars_to_tp1 = outcome.bars_to_tp1
        tracked_until = outcome.tracked_until
        evaluation_status = EvaluationStatus.EVALUATING
        first_barrier = outcome.first_barrier
        success_label = outcome.success_label
        tp2_label = outcome.tp2_label
        invalidated_first = outcome.invalidated_first
        total_bars = starting_bars

        for bar in bars:
            total_bars += 1
            tracked_until = bar.bar_timestamp
            favorable = ((Decimal(bar.high_price) - entry_reference) / entry_reference) * Decimal("100")
            adverse = ((entry_reference - Decimal(bar.low_price)) / entry_reference) * Decimal("100")
            mfe_pct = max(mfe_pct, favorable)
            mae_pct = max(mae_pct, adverse)

            hit_invalidation = Decimal(bar.low_price) <= Decimal(trade_plan.invalidation_level)
            hit_tp1 = Decimal(bar.high_price) >= Decimal(trade_plan.tp1)
            hit_tp2 = Decimal(bar.high_price) >= Decimal(trade_plan.tp2)

            if hit_invalidation and (hit_tp1 or hit_tp2):
                first_barrier = "AMBIGUOUS_SAME_BAR_INVALIDATION"
                success_label = False
                tp2_label = False
                invalidated_first = True
                evaluation_status = EvaluationStatus.FINALIZED
                break
            if hit_tp2:
                first_barrier = "TP2"
                success_label = True
                tp2_label = True
                invalidated_first = False
                if bars_to_tp1 is None:
                    bars_to_tp1 = total_bars
                evaluation_status = EvaluationStatus.FINALIZED
                break
            if hit_tp1:
                first_barrier = "TP1"
                success_label = True
                tp2_label = False
                invalidated_first = False
                if bars_to_tp1 is None:
                    bars_to_tp1 = total_bars
                evaluation_status = EvaluationStatus.FINALIZED
                break
            if hit_invalidation:
                first_barrier = "INVALIDATION"
                success_label = False
                tp2_label = False
                invalidated_first = True
                evaluation_status = EvaluationStatus.FINALIZED
                break

        if evaluation_status != EvaluationStatus.FINALIZED and total_bars >= self.time_barrier_bars:
            evaluation_status = EvaluationStatus.FINALIZED
            first_barrier = first_barrier or "TIME"
            success_label = False
            tp2_label = False
            invalidated_first = False

        outcome.evaluation_status = evaluation_status
        outcome.tracked_until = tracked_until
        outcome.bars_tracked = total_bars
        outcome.first_barrier = first_barrier
        outcome.success_label = success_label
        outcome.tp2_label = tp2_label
        outcome.invalidated_first = invalidated_first
        outcome.mfe_pct = mfe_pct.quantize(Decimal("0.0001"))
        outcome.mae_pct = mae_pct.quantize(Decimal("0.0001"))
        outcome.bars_to_tp1 = bars_to_tp1
        if outcome.evaluation_start is None:
            outcome.evaluation_start = trade_plan.plan_timestamp
        if evaluation_status == EvaluationStatus.FINALIZED:
            outcome.evaluation_end = tracked_until or trade_plan.plan_timestamp
        return 1

    def _trade_row(self, signal: Signal, trade_plan: TradePlan, outcome: Outcome, ticker: str) -> dict:
        return {
            "signal_id": str(signal.id),
            "symbol_id": str(signal.symbol_id),
            "ticker": ticker,
            "signal": signal.signal.value,
            "confidence": format(signal.confidence, "f"),
            "grade": signal.grade.value,
            "setup_state": signal.setup_state,
            "entry_type": trade_plan.entry_type.value,
            "entry_zone_low": format(trade_plan.entry_zone_low, "f"),
            "entry_zone_high": format(trade_plan.entry_zone_high, "f"),
            "confirmation_level": format(trade_plan.confirmation_level, "f"),
            "invalidation_level": format(trade_plan.invalidation_level, "f"),
            "tp1": format(trade_plan.tp1, "f"),
            "tp2": format(trade_plan.tp2, "f"),
            "signal_timestamp": signal.signal_timestamp.isoformat(),
            "known_at": signal.known_at.isoformat(),
            "reason_codes": list(signal.reason_codes),
            "market_regime": signal.extensible_context.get("market_regime"),
            "sector_regime": signal.extensible_context.get("sector_regime"),
            "event_risk_class": signal.extensible_context.get("event_risk_class"),
            "micro_state": signal.extensible_context.get("micro_state"),
            "micro_present": signal.extensible_context.get("micro_present"),
            "micro_trigger_state": signal.extensible_context.get("micro_trigger_state"),
            "micro_used_for_confirmation": signal.extensible_context.get("micro_used_for_confirmation"),
            "outcome_status": outcome.evaluation_status.value,
            "first_barrier": outcome.first_barrier,
            "success_label": outcome.success_label,
            "tp2_label": outcome.tp2_label,
            "invalidated_first": outcome.invalidated_first,
            "bars_tracked": outcome.bars_tracked,
            "bars_to_tp1": outcome.bars_to_tp1,
            "mfe_pct": format(outcome.mfe_pct, "f") if outcome.mfe_pct is not None else None,
            "mae_pct": format(outcome.mae_pct, "f") if outcome.mae_pct is not None else None,
            "tracked_until": outcome.tracked_until.isoformat() if outcome.tracked_until is not None else None,
            "alert_state": signal.extensible_context.get("alert_state"),
            "suppression_reason": signal.extensible_context.get("suppression_reason"),
            "telegram_sendable": signal.extensible_context.get("telegram_sendable"),
            "run_id": signal.extensible_context.get("run_id"),
        }


def _entry_reference_price(entry_zone_low: Decimal, entry_zone_high: Decimal) -> Decimal:
    return (Decimal(entry_zone_low) + Decimal(entry_zone_high)) / Decimal("2")

