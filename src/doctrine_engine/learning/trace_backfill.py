from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from doctrine_engine.db.models.signals import Signal
from doctrine_engine.engines.signal_engine import SignalEngineConfig


@dataclass(frozen=True, slots=True)
class TraceBackfillSummary:
    scanned_rows: int
    updated_rows: int
    cutoff: str


class SignalTraceBackfiller:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        config: SignalEngineConfig | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.config = config or SignalEngineConfig()

    def backfill_recent(self, *, days: int) -> TraceBackfillSummary:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        scanned_rows = 0
        updated_rows = 0
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(Signal)
                    .where(Signal.known_at >= cutoff)
                    .order_by(Signal.known_at.desc())
                )
            )
            for signal in rows:
                scanned_rows += 1
                if self._backfill_signal(signal):
                    updated_rows += 1
            if updated_rows:
                session.commit()
        return TraceBackfillSummary(
            scanned_rows=scanned_rows,
            updated_rows=updated_rows,
            cutoff=cutoff.isoformat(),
        )

    def _backfill_signal(self, signal: Signal) -> bool:
        context = dict(signal.extensible_context or {})
        changed = False

        internal_mtf_state = context.get("internal_mtf_state")
        ltf_trigger_state = context.get("ltf_trigger_state")
        if internal_mtf_state and not context.get("candidate_mtf_states"):
            context["candidate_mtf_states"] = [internal_mtf_state]
            changed = True
        if ltf_trigger_state and not context.get("candidate_ltf_trigger_states"):
            context["candidate_ltf_trigger_states"] = [ltf_trigger_state]
            changed = True
        if not context.get("confidence_components"):
            components = self._derive_confidence_components(signal, context)
            if components:
                context["confidence_components"] = components
                changed = True
        if changed:
            context["trace_backfilled"] = True
            context["trace_backfill_version"] = "lifecycle_trace_v1"
            signal.extensible_context = context
        return changed

    def _derive_confidence_components(self, signal: Signal, context: dict) -> dict[str, str]:
        internal_mtf_state = context.get("internal_mtf_state")
        ltf_trigger_state = context.get("ltf_trigger_state")
        sector_strength = ((context.get("sector_snapshot") or {}).get("sector_strength") or "UNKNOWN").upper()
        event_risk_snapshot = context.get("event_risk_snapshot") or {}
        regime_snapshot = context.get("regime_snapshot") or {}

        components: dict[str, Decimal] = {
            "htf_bias": Decimal("0"),
            "mtf_state": Decimal("0"),
            "ltf_trigger": Decimal("0"),
            "cross_frame_alignment": Decimal("0"),
            "zone_location": Decimal("0"),
            "compression": Decimal("0"),
            "displacement": Decimal("0"),
            "regime_permission": Decimal("0"),
            "sector_strength": Decimal("0"),
            "event_risk_penalty": Decimal("0"),
        }

        bias_value = signal.bias_htf.value if hasattr(signal.bias_htf, "value") else str(signal.bias_htf)
        if bias_value == "BULLISH":
            components["htf_bias"] = self.config.htf_bullish_weight

        mtf_scores = {
            "RECONTAINMENT_CANDIDATE": self.config.mtf_weight_recontainment,
            "BULLISH_RECLAIM": self.config.mtf_weight_reclaim,
            "DISCOUNT_RESPONSE": self.config.mtf_weight_discount,
            "EQUILIBRIUM_HOLD": self.config.mtf_weight_equilibrium,
        }
        ltf_scores = {
            "TRAP_REVERSE_BULLISH": self.config.ltf_weight_trap_reverse,
            "FAKE_BREAKDOWN_REVERSAL": self.config.ltf_weight_fake_breakdown,
            "LTF_BULLISH_RECLAIM": self.config.ltf_weight_reclaim,
            "LTF_BULLISH_CHOCH": self.config.ltf_weight_choch,
            "LTF_BULLISH_BOS": self.config.ltf_weight_bos,
        }
        sector_scores = {
            "STRONG": self.config.sector_strength_bonus_strong,
            "NEUTRAL": self.config.sector_strength_bonus_neutral,
            "WEAK": self.config.sector_strength_bonus_weak,
            "UNKNOWN": self.config.sector_strength_bonus_unknown,
        }

        components["mtf_state"] = mtf_scores.get(str(internal_mtf_state), Decimal("0"))
        components["ltf_trigger"] = ltf_scores.get(str(ltf_trigger_state), Decimal("0"))
        if context.get("cross_frame_aligned"):
            components["cross_frame_alignment"] = self.config.cross_frame_alignment_bonus
        if regime_snapshot.get("allows_longs") is True:
            components["regime_permission"] = self.config.regime_permission_supportive_bonus
        components["sector_strength"] = sector_scores.get(sector_strength, self.config.sector_strength_bonus_unknown)
        if event_risk_snapshot.get("blocked") is True:
            components["event_risk_penalty"] = -self.config.max_event_risk_soft_penalty

        return {key: format(value, "f") for key, value in components.items()}


__all__ = ["SignalTraceBackfiller", "TraceBackfillSummary"]
