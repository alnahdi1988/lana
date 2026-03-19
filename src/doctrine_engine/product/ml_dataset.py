from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.db.models.learning import ModelRun
from doctrine_engine.db.models.signals import Outcome, Signal, TradePlan
from doctrine_engine.db.models.symbols import Symbol


DATASET_VERSION = "lifecycle_v1"
BASELINE_MODEL_NAME = "baseline_empirical_ranker"


@dataclass(frozen=True, slots=True)
class DatasetExportSummary:
    dataset_version: str
    total_rows: int
    pending_rows: int
    finalized_rows: int
    latest_signal_timestamp: str | None
    latest_known_at: str | None


class LifecycleDatasetExporter:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def export_rows(self, *, limit: int | None = None, newest_first: bool = False) -> list[dict]:
        with self.session_factory() as session:
            order_by = (
                (Signal.known_at.desc(), Signal.signal_timestamp.desc(), Signal.created_at.desc())
                if newest_first
                else (Signal.signal_timestamp.asc(), Signal.created_at.asc())
            )
            statement = (
                select(Signal, TradePlan, Outcome, Symbol.ticker)
                .join(TradePlan, TradePlan.signal_id == Signal.id)
                .join(Outcome, Outcome.signal_id == Signal.id)
                .join(Symbol, Symbol.id == Signal.symbol_id)
                .order_by(*order_by)
            )
            if limit is not None:
                statement = statement.limit(limit)
            rows = session.execute(statement).all()
        return [self._export_row(signal, trade_plan, outcome, ticker) for signal, trade_plan, outcome, ticker in rows]

    def export_json(self, output_path: str | Path, *, limit: int | None = None) -> DatasetExportSummary:
        rows = self.export_rows(limit=limit)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return self._summary(rows)

    def summary(self, *, limit: int | None = None) -> DatasetExportSummary:
        return self._summary(self.export_rows(limit=limit))

    def record_model_run(
        self,
        *,
        model_version: str,
        status: str,
        training_window_start: datetime | None,
        training_window_end: datetime | None,
        validation_window_start: datetime | None,
        validation_window_end: datetime | None,
        metrics: dict,
        params: dict,
        artifact_uri: str | None,
        notes: str | None = None,
        promoted: bool = False,
    ) -> ModelRun:
        with self.session_factory() as session:
            run = ModelRun(
                model_name=BASELINE_MODEL_NAME,
                model_version=model_version,
                feature_set_version=DATASET_VERSION,
                status=status,
                training_window_start=training_window_start,
                training_window_end=training_window_end,
                validation_window_start=validation_window_start,
                validation_window_end=validation_window_end,
                artifact_uri=artifact_uri,
                metrics=dict(metrics),
                params=dict(params),
                notes=notes,
                promoted=promoted,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
        return run

    def _summary(self, rows: list[dict]) -> DatasetExportSummary:
        latest_row = max(rows, key=lambda row: (row["known_at"], row["signal_timestamp"])) if rows else None
        latest_signal_timestamp = latest_row["signal_timestamp"] if latest_row else None
        latest_known_at = latest_row["known_at"] if latest_row else None
        pending_rows = sum(1 for row in rows if row["evaluation_status"] == "PENDING")
        finalized_rows = sum(1 for row in rows if row["evaluation_status"] == "FINALIZED")
        return DatasetExportSummary(
            dataset_version=DATASET_VERSION,
            total_rows=len(rows),
            pending_rows=pending_rows,
            finalized_rows=finalized_rows,
            latest_signal_timestamp=latest_signal_timestamp,
            latest_known_at=latest_known_at,
        )

    def _export_row(self, signal: Signal, trade_plan: TradePlan, outcome: Outcome, ticker: str) -> dict:
        return {
            "dataset_version": DATASET_VERSION,
            "signal_id": str(signal.id),
            "symbol_id": str(signal.symbol_id),
            "ticker": ticker,
            "signal_timestamp": signal.signal_timestamp.isoformat(),
            "known_at": signal.known_at.isoformat(),
            "signal": signal.signal.value,
            "confidence": _text(signal.confidence),
            "grade": signal.grade.value,
            "bias_htf": signal.bias_htf.value,
            "setup_state": signal.setup_state,
            "reason_codes": list(signal.reason_codes),
            "event_risk_blocked": signal.event_risk_blocked,
            "internal_mtf_state": signal.extensible_context.get("internal_mtf_state"),
            "candidate_mtf_states": list(signal.extensible_context.get("candidate_mtf_states") or []),
            "ltf_trigger_state": signal.extensible_context.get("ltf_trigger_state"),
            "candidate_ltf_trigger_states": list(signal.extensible_context.get("candidate_ltf_trigger_states") or []),
            "cross_frame_aligned": signal.extensible_context.get("cross_frame_aligned"),
            "hard_gates": dict(signal.extensible_context.get("hard_gates") or {}),
            "confidence_components": dict(signal.extensible_context.get("confidence_components") or {}),
            "market_regime": signal.extensible_context.get("market_regime"),
            "sector_regime": signal.extensible_context.get("sector_regime"),
            "event_risk_class": signal.extensible_context.get("event_risk_class"),
            "micro_state": signal.extensible_context.get("micro_state"),
            "micro_present": signal.extensible_context.get("micro_present"),
            "micro_trigger_state": signal.extensible_context.get("micro_trigger_state"),
            "micro_used_for_confirmation": signal.extensible_context.get("micro_used_for_confirmation"),
            "alert_state": signal.extensible_context.get("alert_state"),
            "suppression_reason": signal.extensible_context.get("suppression_reason"),
            "telegram_sendable": signal.extensible_context.get("telegram_sendable"),
            "run_id": signal.extensible_context.get("run_id"),
            "entry_type": trade_plan.entry_type.value,
            "entry_zone_low": _text(trade_plan.entry_zone_low),
            "entry_zone_high": _text(trade_plan.entry_zone_high),
            "confirmation_level": _text(trade_plan.confirmation_level),
            "invalidation_level": _text(trade_plan.invalidation_level),
            "tp1": _text(trade_plan.tp1),
            "tp2": _text(trade_plan.tp2),
            "plan_reason_codes": list(trade_plan.plan_reason_codes),
            "evaluation_status": outcome.evaluation_status.value,
            "evaluation_start": outcome.evaluation_start.isoformat() if outcome.evaluation_start is not None else None,
            "evaluation_end": outcome.evaluation_end.isoformat() if outcome.evaluation_end is not None else None,
            "tracked_until": outcome.tracked_until.isoformat() if outcome.tracked_until is not None else None,
            "bars_tracked": outcome.bars_tracked,
            "first_barrier": outcome.first_barrier,
            "success_label": outcome.success_label,
            "tp2_label": outcome.tp2_label,
            "invalidated_first": outcome.invalidated_first,
            "mfe_pct": _text(outcome.mfe_pct),
            "mae_pct": _text(outcome.mae_pct),
            "bars_to_tp1": outcome.bars_to_tp1,
            "tracking_timeframe": outcome.extensible_context.get("tracking_timeframe"),
            "time_barrier_bars": outcome.extensible_context.get("time_barrier_bars"),
            "entry_reference_mode": outcome.extensible_context.get("entry_reference_mode"),
        }


def _text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


__all__ = [
    "BASELINE_MODEL_NAME",
    "DATASET_VERSION",
    "DatasetExportSummary",
    "LifecycleDatasetExporter",
]
