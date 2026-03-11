from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal

from doctrine_engine.alerts.models import (
    AlertDecisionPayload,
    AlertDecisionResult,
    AlertPriority,
    AlertWorkflowInput,
    SnapshotRenderRequest,
)


@dataclass(frozen=True, slots=True)
class AlertWorkflowConfig:
    cooldown_minutes: int = 60


class AlertWorkflow:
    def __init__(self, config: AlertWorkflowConfig | None = None) -> None:
        self.config = config or AlertWorkflowConfig()

    def evaluate(self, workflow_input: AlertWorkflowInput) -> AlertDecisionResult:
        self._validate_input(workflow_input)

        signal_result = workflow_input.signal_result
        trade_plan_result = workflow_input.trade_plan_result

        priority = self._priority(signal_result.grade)
        dedup_key = str(workflow_input.signal_id)
        family_key = self._family_key(
            symbol_id=signal_result.symbol_id,
            setup_state=signal_result.setup_state,
            entry_type=trade_plan_result.entry_type,
        )

        payload = AlertDecisionPayload(
            symbol_id=signal_result.symbol_id,
            ticker=signal_result.ticker,
            signal=signal_result.signal,
            confidence=signal_result.confidence,
            grade=signal_result.grade,
            setup_state=signal_result.setup_state,
            entry_type=trade_plan_result.entry_type,
            entry_zone_low=trade_plan_result.entry_zone_low,
            entry_zone_high=trade_plan_result.entry_zone_high,
            confirmation_level=trade_plan_result.confirmation_level,
            invalidation_level=trade_plan_result.invalidation_level,
            tp1=trade_plan_result.tp1,
            tp2=trade_plan_result.tp2,
            signal_timestamp=signal_result.signal_timestamp,
            known_at=signal_result.known_at,
            alert_state="SUPPRESSED",
            priority=priority,
            operator_summary="",
            reason_codes=list(signal_result.reason_codes),
            snapshot_path=None,
        )
        payload = replace(payload, operator_summary=self._operator_summary(payload))
        payload_fingerprint = self._payload_fingerprint(payload)

        sendability = self._sendability(signal_result.signal, signal_result.grade, signal_result.event_risk_blocked)
        if sendability is not None:
            payload = replace(payload, alert_state="SUPPRESSED")
            return AlertDecisionResult(
                send=False,
                alert_state="SUPPRESSED",
                suppression_reason=sendability,
                priority=priority,
                dedup_key=dedup_key,
                family_key=family_key,
                payload_fingerprint=payload_fingerprint,
                payload=payload,
                snapshot_request=None,
            )

        prior_state = workflow_input.prior_alert_state
        cooldown_active = self._cooldown_active(prior_state, payload.known_at)

        if prior_state is not None and prior_state.signal_id == workflow_input.signal_id:
            payload = replace(payload, alert_state="DUPLICATE_BLOCKED")
            return AlertDecisionResult(
                send=False,
                alert_state="DUPLICATE_BLOCKED",
                suppression_reason="DUPLICATE_SIGNAL",
                priority=priority,
                dedup_key=dedup_key,
                family_key=family_key,
                payload_fingerprint=payload_fingerprint,
                payload=payload,
                snapshot_request=None,
            )

        if (
            prior_state is not None
            and prior_state.family_key == family_key
            and prior_state.payload_fingerprint == payload_fingerprint
            and cooldown_active
        ):
            payload = replace(payload, alert_state="DUPLICATE_BLOCKED")
            return AlertDecisionResult(
                send=False,
                alert_state="DUPLICATE_BLOCKED",
                suppression_reason="DUPLICATE_SIGNAL",
                priority=priority,
                dedup_key=dedup_key,
                family_key=family_key,
                payload_fingerprint=payload_fingerprint,
                payload=payload,
                snapshot_request=None,
            )

        if prior_state is not None and cooldown_active and self._is_upgrade(prior_state, payload):
            payload = replace(payload, alert_state="UPGRADED")
            return AlertDecisionResult(
                send=True,
                alert_state="UPGRADED",
                suppression_reason=None,
                priority=priority,
                dedup_key=dedup_key,
                family_key=family_key,
                payload_fingerprint=payload_fingerprint,
                payload=payload,
                snapshot_request=self._snapshot_request(workflow_input, payload),
            )

        if prior_state is not None and prior_state.family_key == family_key and cooldown_active:
            payload = replace(payload, alert_state="COOLDOWN_BLOCKED")
            return AlertDecisionResult(
                send=False,
                alert_state="COOLDOWN_BLOCKED",
                suppression_reason="COOLDOWN_ACTIVE",
                priority=priority,
                dedup_key=dedup_key,
                family_key=family_key,
                payload_fingerprint=payload_fingerprint,
                payload=payload,
                snapshot_request=None,
            )

        payload = replace(payload, alert_state="NEW")
        return AlertDecisionResult(
            send=True,
            alert_state="NEW",
            suppression_reason=None,
            priority=priority,
            dedup_key=dedup_key,
            family_key=family_key,
            payload_fingerprint=payload_fingerprint,
            payload=payload,
            snapshot_request=self._snapshot_request(workflow_input, payload),
        )

    def _validate_input(self, workflow_input: AlertWorkflowInput) -> None:
        signal_result = workflow_input.signal_result
        trade_plan_result = workflow_input.trade_plan_result
        if trade_plan_result.signal_id != workflow_input.signal_id:
            raise ValueError("Trade plan signal_id must match workflow signal_id.")
        if trade_plan_result.symbol_id != signal_result.symbol_id:
            raise ValueError("Trade plan symbol_id must match signal result symbol_id.")
        if trade_plan_result.ticker != signal_result.ticker:
            raise ValueError("Trade plan ticker must match signal result ticker.")
        if trade_plan_result.plan_timestamp != signal_result.signal_timestamp:
            raise ValueError("Trade plan timestamp must match signal timestamp.")
        if trade_plan_result.known_at != signal_result.known_at:
            raise ValueError("Trade plan known_at must match signal known_at.")

    def _priority(self, grade: str) -> AlertPriority:
        if grade == "A+":
            return "PRIORITY"
        if grade == "A":
            return "STANDARD"
        return "LOG_ONLY"

    def _family_key(self, *, symbol_id: uuid.UUID, setup_state: str, entry_type: str) -> str:
        return f"{symbol_id}:{setup_state}:{entry_type}"

    def _operator_summary(self, payload: AlertDecisionPayload) -> str:
        return (
            f"{payload.priority} {payload.grade} LONG {payload.ticker} | "
            f"{payload.setup_state} | {payload.entry_type} | "
            f"zone {self._decimal_text(payload.entry_zone_low)}-{self._decimal_text(payload.entry_zone_high)} | "
            f"invalid {self._decimal_text(payload.invalidation_level)} | "
            f"known {payload.known_at.isoformat()}"
        )

    def _payload_fingerprint(self, payload: AlertDecisionPayload) -> str:
        parts = (
            payload.ticker,
            payload.signal,
            payload.grade,
            payload.setup_state,
            payload.entry_type,
            self._decimal_text(payload.entry_zone_low),
            self._decimal_text(payload.entry_zone_high),
            self._decimal_text(payload.confirmation_level),
            self._decimal_text(payload.invalidation_level),
            self._decimal_text(payload.tp1),
            self._decimal_text(payload.tp2),
        )
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def _sendability(self, signal: str, grade: str, event_risk_blocked: bool) -> str | None:
        if signal != "LONG":
            return "NOT_LONG"
        if grade not in {"A+", "A"}:
            return "GRADE_NOT_SENDABLE"
        if event_risk_blocked:
            return "EVENT_RISK_BLOCKED"
        return None

    def _cooldown_active(self, prior_state, current_known_at) -> bool:
        if prior_state is None:
            return False
        return current_known_at < prior_state.sent_at + timedelta(minutes=self.config.cooldown_minutes)

    def _is_upgrade(self, prior_state, payload: AlertDecisionPayload) -> bool:
        if prior_state.grade == "A" and payload.grade == "A+":
            return True
        if (
            prior_state.ticker == payload.ticker
            and prior_state.setup_state == payload.setup_state
            and prior_state.entry_type == "BASE"
            and payload.entry_type == "CONFIRMATION"
        ):
            return True
        return False

    def _snapshot_request(
        self,
        workflow_input: AlertWorkflowInput,
        payload: AlertDecisionPayload,
    ) -> SnapshotRenderRequest | None:
        snapshot_config = workflow_input.snapshot_request_config
        if snapshot_config is None or not snapshot_config.enabled:
            return None
        return SnapshotRenderRequest(
            signal_id=workflow_input.signal_id,
            ticker=payload.ticker,
            signal_timestamp=payload.signal_timestamp,
            known_at=payload.known_at,
            entry_zone_low=payload.entry_zone_low,
            entry_zone_high=payload.entry_zone_high,
            confirmation_level=payload.confirmation_level,
            invalidation_level=payload.invalidation_level,
            tp1=payload.tp1,
            tp2=payload.tp2,
            output_dir=snapshot_config.output_dir,
            include_timeframes=snapshot_config.include_timeframes,
            bars_per_frame=snapshot_config.bars_per_frame,
        )

    def _decimal_text(self, value: Decimal) -> str:
        return format(value, "f")
