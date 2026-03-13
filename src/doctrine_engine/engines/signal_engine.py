from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
import logging

from doctrine_engine.engines.models import (
    LTFTriggerState,
    MicroState,
    OutputSetupState,
    SignalBias,
    SignalEngineInput,
    SignalEngineResult,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SignalEngineConfig:
    signal_version: str = "v1"
    long_confidence_threshold: Decimal = Decimal("0.70")
    require_micro_confirmation: bool = False
    micro_context_requested: bool = False
    fail_closed_event_risk: bool = False
    fail_closed_regime: bool = False
    htf_bearish_event_lookback_bars: int = 3
    mtf_invalidation_lookback_bars: int = 1
    ltf_structure_trigger_freshness_bars: int = 1
    micro_trigger_freshness_bars: int = 1
    grade_a_plus_threshold: Decimal = Decimal("0.90")
    grade_a_threshold: Decimal = Decimal("0.80")
    grade_b_threshold: Decimal = Decimal("0.70")


class SignalEngine:
    def __init__(self, config: SignalEngineConfig | None = None) -> None:
        self.config = config or SignalEngineConfig()

    def evaluate(self, signal_input: SignalEngineInput) -> SignalEngineResult:
        self._validate_input(signal_input)

        price_in_range = Decimal("5") <= signal_input.price_reference <= Decimal("50")
        price_code = "PRICE_RANGE_VALID" if price_in_range else "PRICE_OUT_OF_RANGE"
        universe_code = "UNIVERSE_ELIGIBLE" if signal_input.universe_eligible else "UNIVERSE_REJECTED"

        bias_htf = self._determine_htf_bias(signal_input)
        htf_code = {
            "BULLISH": "HTF_BULLISH_STRUCTURE",
            "NEUTRAL": "HTF_UNCLEAR",
            "BEARISH": "HTF_BEARISH",
        }[bias_htf]

        internal_mtf_state = self._determine_internal_mtf_state(signal_input)
        mtf_code = self._mtf_reason_code(internal_mtf_state)

        ltf_trigger_state = self._determine_trigger_state(
            signal_input.ltf,
            self.config.ltf_structure_trigger_freshness_bars,
        )
        ltf_code = self._ltf_reason_code(ltf_trigger_state)

        micro_requested = self.config.require_micro_confirmation or self.config.micro_context_requested
        micro_present = signal_input.micro is not None
        micro_used = self.config.require_micro_confirmation and micro_present
        micro_trigger_state = (
            self._determine_trigger_state(signal_input.micro, self.config.micro_trigger_freshness_bars)
            if micro_present
            else None
        )
        micro_state: MicroState = self._micro_state(
            micro_requested=micro_requested,
            micro_present=micro_present,
            micro_used=micro_used,
        )
        if micro_present and not micro_used:
            LOGGER.debug("5M micro context present but not used for confirmation for %s.", signal_input.ticker)

        event_risk_blocked = signal_input.event_risk.blocked is True
        event_risk_incomplete_block = (
            not signal_input.event_risk.coverage_complete and self.config.fail_closed_event_risk
        )
        regime_explicit_block = signal_input.regime.allows_longs is False
        regime_incomplete_block = (
            not signal_input.regime.coverage_complete and self.config.fail_closed_regime
        )

        cross_frame_aligned = (
            bias_htf == "BULLISH"
            and internal_mtf_state in {
                "RECONTAINMENT_CANDIDATE",
                "BULLISH_RECLAIM",
                "DISCOUNT_RESPONSE",
                "EQUILIBRIUM_HOLD",
            }
            and ltf_trigger_state != "LTF_NO_TRIGGER"
            and (
                not self.config.require_micro_confirmation
                or (micro_present and micro_trigger_state != "LTF_NO_TRIGGER")
            )
        )
        alignment_code = "CROSS_FRAME_ALIGNMENT" if cross_frame_aligned else "NO_CROSS_FRAME_CONFIRMATION"

        regime_allowed = (
            signal_input.regime.allows_longs is not False
            and not regime_incomplete_block
        )
        regime_code = "REGIME_ALLOWED" if regime_allowed else "REGIME_BLOCKED"

        event_risk_clear = not event_risk_blocked and not event_risk_incomplete_block
        event_risk_code = "EVENT_RISK_CLEAR" if event_risk_clear else "EVENT_RISK_BLOCKED"

        confidence = self._compute_confidence(
            signal_input=signal_input,
            bias_htf=bias_htf,
            internal_mtf_state=internal_mtf_state,
            ltf_trigger_state=ltf_trigger_state,
            cross_frame_aligned=cross_frame_aligned,
        )

        hard_gates = {
            "price_in_range": price_in_range,
            "universe_eligible": signal_input.universe_eligible,
            "event_risk_not_blocked": not event_risk_blocked and not event_risk_incomplete_block,
            "regime_not_blocked": not regime_explicit_block and not regime_incomplete_block,
            "htf_bullish": bias_htf == "BULLISH",
            "mtf_valid": internal_mtf_state in {
                "RECONTAINMENT_CANDIDATE",
                "BULLISH_RECLAIM",
                "DISCOUNT_RESPONSE",
                "EQUILIBRIUM_HOLD",
            },
            "ltf_trigger": ltf_trigger_state != "LTF_NO_TRIGGER",
            "micro_trigger": (
                True
                if not self.config.require_micro_confirmation
                else micro_present and micro_trigger_state != "LTF_NO_TRIGGER"
            ),
            "cross_frame_aligned": cross_frame_aligned,
            "confidence_threshold": confidence >= self.config.long_confidence_threshold,
        }

        signal_value = "LONG" if all(hard_gates.values()) else "NONE"
        grade = self._grade(confidence) if signal_value == "LONG" else "IGNORE"
        setup_state = self._output_setup_state(internal_mtf_state, cross_frame_aligned)

        signal_timestamp = (
            signal_input.micro.latest_bar.bar_timestamp
            if micro_used
            else signal_input.ltf.latest_bar.bar_timestamp
        )
        known_at = max(self._consumed_known_ats(signal_input))

        caution_codes: list[str] = []
        if signal_input.sector_context.sector_strength == "WEAK":
            caution_codes.append("SECTOR_WEAK")
        if self.config.require_micro_confirmation and signal_input.micro is None:
            caution_codes.append("MICRO_CONFIRMATION_MISSING")

        reason_codes = [
            price_code,
            universe_code,
            htf_code,
            mtf_code,
            ltf_code,
            alignment_code,
            regime_code,
            event_risk_code,
            *caution_codes,
        ]

        return SignalEngineResult(
            symbol_id=signal_input.symbol_id,
            ticker=signal_input.ticker,
            universe_snapshot_id=signal_input.universe_snapshot_id,
            signal_timestamp=signal_timestamp,
            known_at=known_at,
            htf_bar_timestamp=signal_input.htf.latest_bar.bar_timestamp,
            mtf_bar_timestamp=signal_input.mtf.latest_bar.bar_timestamp,
            ltf_bar_timestamp=signal_input.ltf.latest_bar.bar_timestamp,
            signal=signal_value,
            signal_version=self.config.signal_version,
            confidence=confidence,
            grade=grade,
            bias_htf=bias_htf,
            setup_state=setup_state,
            reason_codes=reason_codes,
            event_risk_blocked=event_risk_blocked,
            extensible_context={
                "internal_mtf_state": internal_mtf_state,
                "ltf_trigger_state": ltf_trigger_state,
                "market_regime": signal_input.regime.market_regime,
                "sector_regime": signal_input.regime.sector_regime,
                "event_risk_class": signal_input.event_risk.event_risk_class,
                "micro_state": micro_state,
                "micro_trigger_state": micro_trigger_state,
                "micro_present": micro_present,
                "micro_used_for_confirmation": micro_used,
                "cross_frame_aligned": cross_frame_aligned,
                "consumed_known_at": [known_at.isoformat() for known_at in self._consumed_known_ats(signal_input)],
                "regime_snapshot": {
                    "market_regime": signal_input.regime.market_regime,
                    "sector_regime": signal_input.regime.sector_regime,
                    "coverage_complete": signal_input.regime.coverage_complete,
                    "allows_longs": signal_input.regime.allows_longs,
                },
                "event_risk_snapshot": {
                    "event_risk_class": signal_input.event_risk.event_risk_class,
                    "coverage_complete": signal_input.event_risk.coverage_complete,
                    "blocked": signal_input.event_risk.blocked,
                    "reason_codes": list(signal_input.event_risk.reason_codes),
                },
                "sector_snapshot": {
                    "sector_strength": signal_input.sector_context.sector_strength,
                    "relative_strength_score": (
                        str(signal_input.sector_context.relative_strength_score)
                        if signal_input.sector_context.relative_strength_score is not None
                        else None
                    ),
                },
                "hard_gates": hard_gates,
            },
        )

    def _validate_input(self, signal_input: SignalEngineInput) -> None:
        frame_expectations = {
            "4H": signal_input.htf,
            "1H": signal_input.mtf,
            "15M": signal_input.ltf,
        }
        for timeframe, frame in frame_expectations.items():
            if frame.timeframe != timeframe:
                raise ValueError(f"Expected {timeframe} frame input.")
            if not frame.structure_history:
                raise ValueError(f"{timeframe} structure history cannot be empty.")
            if frame.structure_history[-1].bar_timestamp != frame.structure.bar_timestamp:
                raise ValueError(f"{timeframe} latest structure must match structure_history[-1].")
        if signal_input.micro is not None:
            if signal_input.micro.timeframe != "5M":
                raise ValueError("Micro input must use timeframe 5M.")
            if not signal_input.micro.structure_history:
                raise ValueError("5M structure history cannot be empty when micro input is present.")
            if signal_input.micro.structure_history[-1].bar_timestamp != signal_input.micro.structure.bar_timestamp:
                raise ValueError("5M latest structure must match structure_history[-1].")

    def _determine_htf_bias(self, signal_input: SignalEngineInput) -> SignalBias:
        if signal_input.htf.structure.trend_state == "BEARISH_SEQUENCE":
            return "BEARISH"

        recent_results = signal_input.htf.structure_history[-self.config.htf_bearish_event_lookback_bars :]
        if self._recent_has_bearish_structure_event(recent_results):
            return "BEARISH"

        if (
            signal_input.htf.structure.trend_state == "BULLISH_SEQUENCE"
            and signal_input.htf.zone.range_status == "RANGE_AVAILABLE"
        ):
            return "BULLISH"

        return "NEUTRAL"

    def _determine_internal_mtf_state(self, signal_input: SignalEngineInput) -> str:
        recent_results = signal_input.mtf.structure_history[-self.config.mtf_invalidation_lookback_bars :]
        if (
            signal_input.mtf.zone.range_status == "NO_VALID_RANGE"
            or signal_input.mtf.pattern.recontainment.status == "INVALIDATED"
            or self._recent_has_bearish_structure_event(recent_results)
        ):
            return "INVALIDATED"
        if signal_input.mtf.zone.zone_location == "PREMIUM":
            return "EXTENDED_PREMIUM"
        if signal_input.mtf.pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}:
            return "RECONTAINMENT_CANDIDATE"
        if signal_input.mtf.pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
            return "BULLISH_RECLAIM"
        if (
            signal_input.mtf.zone.zone_location == "DISCOUNT"
            and (
                signal_input.mtf.pattern.bullish_fake_breakdown.status in {"NEW_EVENT", "ACTIVE"}
                or signal_input.mtf.pattern.bullish_reclaim.status in {"CANDIDATE", "NEW_EVENT", "ACTIVE"}
            )
        ):
            return "DISCOUNT_RESPONSE"
        if (
            signal_input.mtf.zone.zone_location == "EQUILIBRIUM"
            and (
                signal_input.mtf.pattern.compression.status == "COMPRESSED"
                or signal_input.mtf.pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}
                or signal_input.mtf.pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}
            )
        ):
            return "EQUILIBRIUM_HOLD"
        if signal_input.mtf.structure.trend_state == "MIXED":
            return "CHOP"
        return "NO_STRUCTURE"

    def _determine_trigger_state(
        self,
        frame_input,
        structure_freshness_bars: int,
    ) -> LTFTriggerState:
        if frame_input.pattern.bullish_trap_reverse.status in {"NEW_EVENT", "ACTIVE"}:
            return "TRAP_REVERSE_BULLISH"
        if frame_input.pattern.bullish_fake_breakdown.status in {"NEW_EVENT", "ACTIVE"}:
            return "FAKE_BREAKDOWN_REVERSAL"
        if frame_input.pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
            return "LTF_BULLISH_RECLAIM"

        recent_results = frame_input.structure_history[-structure_freshness_bars:]
        if self._recent_has_structure_event(recent_results, "BULLISH_CHOCH"):
            return "LTF_BULLISH_CHOCH"
        if self._recent_has_structure_event(recent_results, "BULLISH_BOS"):
            return "LTF_BULLISH_BOS"
        return "LTF_NO_TRIGGER"

    def _recent_has_bearish_structure_event(self, results) -> bool:
        return any(
            event.event_type in {"BEARISH_BOS", "BEARISH_CHOCH"}
            for result in results
            for event in result.events_on_bar
        )

    def _recent_has_structure_event(self, results, event_type: str) -> bool:
        return any(
            event.event_type == event_type
            for result in results
            for event in result.events_on_bar
        )

    def _compute_confidence(
        self,
        signal_input: SignalEngineInput,
        bias_htf: SignalBias,
        internal_mtf_state: str,
        ltf_trigger_state: LTFTriggerState,
        cross_frame_aligned: bool,
    ) -> Decimal:
        score = Decimal("0")
        if bias_htf == "BULLISH":
            score += Decimal("0.20")

        mtf_scores = {
            "RECONTAINMENT_CANDIDATE": Decimal("0.20"),
            "BULLISH_RECLAIM": Decimal("0.18"),
            "DISCOUNT_RESPONSE": Decimal("0.16"),
            "EQUILIBRIUM_HOLD": Decimal("0.14"),
        }
        score += mtf_scores.get(internal_mtf_state, Decimal("0"))

        ltf_scores = {
            "TRAP_REVERSE_BULLISH": Decimal("0.15"),
            "FAKE_BREAKDOWN_REVERSAL": Decimal("0.14"),
            "LTF_BULLISH_RECLAIM": Decimal("0.12"),
            "LTF_BULLISH_CHOCH": Decimal("0.10"),
            "LTF_BULLISH_BOS": Decimal("0.08"),
        }
        score += ltf_scores.get(ltf_trigger_state, Decimal("0"))

        if cross_frame_aligned:
            score += Decimal("0.10")

        if signal_input.mtf.zone.zone_location == "DISCOUNT":
            score += Decimal("0.05")
        elif signal_input.mtf.zone.zone_location == "EQUILIBRIUM":
            score += Decimal("0.03")

        if signal_input.mtf.pattern.compression.status == "COMPRESSED":
            score += Decimal("0.03")
        if (
            signal_input.htf.pattern.bullish_displacement.status in {"NEW_EVENT", "ACTIVE"}
            or signal_input.mtf.pattern.bullish_displacement.status in {"NEW_EVENT", "ACTIVE"}
        ):
            score += Decimal("0.02")

        if signal_input.regime.allows_longs is True:
            if (
                signal_input.regime.market_permission_score is not None
                and signal_input.regime.market_permission_score >= Decimal("0.70")
                and signal_input.regime.sector_permission_score is not None
                and signal_input.regime.sector_permission_score >= Decimal("0.60")
            ):
                score += Decimal("0.05")
            else:
                score += Decimal("0.02")

        sector_scores = {
            "STRONG": Decimal("0.03"),
            "NEUTRAL": Decimal("0.01"),
            "WEAK": Decimal("0.00"),
            "UNKNOWN": Decimal("0.00"),
        }
        score += sector_scores[signal_input.sector_context.sector_strength]
        score -= min(Decimal("0.10"), signal_input.event_risk.soft_penalty)
        return max(Decimal("0.00"), min(Decimal("1.00"), score.quantize(Decimal("0.0001"))))

    def _mtf_reason_code(self, internal_mtf_state: str) -> str:
        return {
            "RECONTAINMENT_CANDIDATE": "MTF_RECONTAINMENT_CONFIRMED",
            "BULLISH_RECLAIM": "MTF_BULLISH_RECLAIM",
            "DISCOUNT_RESPONSE": "MTF_DISCOUNT_RESPONSE",
            "EQUILIBRIUM_HOLD": "MTF_EQUILIBRIUM_HOLD",
            "INVALIDATED": "MTF_INVALIDATED",
            "EXTENDED_PREMIUM": "EXTENDED_FROM_EQUILIBRIUM",
            "CHOP": "LOW_STRUCTURAL_QUALITY",
            "NO_STRUCTURE": "LOW_STRUCTURAL_QUALITY",
        }[internal_mtf_state]

    def _ltf_reason_code(self, ltf_trigger_state: LTFTriggerState) -> str:
        return {
            "TRAP_REVERSE_BULLISH": "TRAP_REVERSE_BULLISH",
            "FAKE_BREAKDOWN_REVERSAL": "FAKE_BREAKDOWN_REVERSAL",
            "LTF_BULLISH_RECLAIM": "LTF_BULLISH_RECLAIM",
            "LTF_BULLISH_CHOCH": "LTF_BULLISH_CHOCH",
            "LTF_BULLISH_BOS": "LTF_BULLISH_BOS",
            "LTF_NO_TRIGGER": "LTF_NO_TRIGGER",
        }[ltf_trigger_state]

    def _output_setup_state(self, internal_mtf_state: str, cross_frame_aligned: bool) -> OutputSetupState:
        if internal_mtf_state == "RECONTAINMENT_CANDIDATE" and cross_frame_aligned:
            return "RECONTAINMENT_CONFIRMED"
        if internal_mtf_state == "BULLISH_RECLAIM" and cross_frame_aligned:
            return "BULLISH_RECLAIM"
        if internal_mtf_state == "DISCOUNT_RESPONSE" and cross_frame_aligned:
            return "DISCOUNT_RESPONSE"
        if internal_mtf_state == "EQUILIBRIUM_HOLD" and cross_frame_aligned:
            return "EQUILIBRIUM_HOLD"
        if internal_mtf_state == "INVALIDATED":
            return "INVALIDATED"
        if internal_mtf_state == "EXTENDED_PREMIUM":
            return "EXTENDED_PREMIUM"
        if internal_mtf_state == "CHOP":
            return "CHOP"
        return "NO_VALID_LONG_STRUCTURE"

    def _grade(self, confidence: Decimal) -> str:
        if confidence >= self.config.grade_a_plus_threshold:
            return "A+"
        if confidence >= self.config.grade_a_threshold:
            return "A"
        if confidence >= self.config.grade_b_threshold:
            return "B"
        return "IGNORE"

    def _consumed_known_ats(self, signal_input: SignalEngineInput) -> list[datetime]:
        known_ats = [
            signal_input.universe_known_at,
            signal_input.htf.latest_bar.known_at,
            signal_input.mtf.latest_bar.known_at,
            signal_input.ltf.latest_bar.known_at,
            signal_input.regime.known_at,
            signal_input.event_risk.known_at,
            signal_input.sector_context.known_at,
        ]
        if self.config.require_micro_confirmation and signal_input.micro is not None:
            known_ats.append(signal_input.micro.latest_bar.known_at)
        return known_ats

    @staticmethod
    def _micro_state(*, micro_requested: bool, micro_present: bool, micro_used: bool) -> MicroState:
        if not micro_requested:
            return "NOT_REQUESTED"
        if not micro_present:
            return "REQUESTED_UNAVAILABLE"
        if micro_used:
            return "AVAILABLE_USED"
        return "AVAILABLE_NOT_USED"
