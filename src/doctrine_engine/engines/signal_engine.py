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
    universe_min_price: Decimal = Decimal("5")
    universe_max_price: Decimal = Decimal("50")
    htf_timeframe: str = "4H"
    mtf_timeframe: str = "1H"
    ltf_timeframe: str = "15M"
    micro_timeframe: str = "5M"
    htf_bullish_weight: Decimal = Decimal("0.20")
    mtf_weight_recontainment: Decimal = Decimal("0.20")
    mtf_weight_reclaim: Decimal = Decimal("0.20")
    mtf_weight_discount: Decimal = Decimal("0.16")
    mtf_weight_equilibrium: Decimal = Decimal("0.14")
    ltf_weight_trap_reverse: Decimal = Decimal("0.15")
    ltf_weight_fake_breakdown: Decimal = Decimal("0.14")
    ltf_weight_reclaim: Decimal = Decimal("0.12")
    ltf_weight_choch: Decimal = Decimal("0.10")
    ltf_weight_bos: Decimal = Decimal("0.08")
    cross_frame_alignment_bonus: Decimal = Decimal("0.10")
    discount_zone_bonus: Decimal = Decimal("0.05")
    equilibrium_zone_bonus: Decimal = Decimal("0.03")
    compression_bonus: Decimal = Decimal("0.03")
    displacement_bonus: Decimal = Decimal("0.02")
    regime_market_permission_strong_threshold: Decimal = Decimal("0.70")
    regime_sector_permission_strong_threshold: Decimal = Decimal("0.60")
    regime_permission_strong_bonus: Decimal = Decimal("0.05")
    regime_permission_supportive_bonus: Decimal = Decimal("0.02")
    sector_strength_bonus_strong: Decimal = Decimal("0.03")
    sector_strength_bonus_neutral: Decimal = Decimal("0.01")
    sector_strength_bonus_weak: Decimal = Decimal("0.00")
    sector_strength_bonus_unknown: Decimal = Decimal("0.00")
    max_event_risk_soft_penalty: Decimal = Decimal("0.10")


class SignalEngine:
    def __init__(self, config: SignalEngineConfig | None = None) -> None:
        self.config = config or SignalEngineConfig()

    def evaluate(self, signal_input: SignalEngineInput) -> SignalEngineResult:
        self._validate_input(signal_input)

        price_in_range = self.config.universe_min_price <= signal_input.price_reference <= self.config.universe_max_price
        price_code = "PRICE_RANGE_VALID" if price_in_range else "PRICE_OUT_OF_RANGE"
        universe_code = "UNIVERSE_ELIGIBLE" if signal_input.universe_eligible else "UNIVERSE_REJECTED"

        bias_htf = self._determine_htf_bias(signal_input)
        htf_code = {
            "BULLISH": "HTF_BULLISH_STRUCTURE",
            "NEUTRAL": "HTF_UNCLEAR",
            "BEARISH": "HTF_BEARISH",
        }[bias_htf]

        candidate_mtf_states = self._candidate_internal_mtf_states(signal_input)
        internal_mtf_state = candidate_mtf_states[0]
        mtf_code = self._mtf_reason_code(internal_mtf_state)

        candidate_ltf_trigger_states = self._candidate_trigger_states(
            signal_input.ltf,
            self.config.ltf_structure_trigger_freshness_bars,
        )
        ltf_trigger_state = candidate_ltf_trigger_states[0]
        ltf_code = self._ltf_reason_code(ltf_trigger_state)

        micro_requested = self.config.require_micro_confirmation or self.config.micro_context_requested
        micro_present = signal_input.micro is not None
        micro_used = self.config.require_micro_confirmation and micro_present
        micro_trigger_state = (
            self._candidate_trigger_states(signal_input.micro, self.config.micro_trigger_freshness_bars)[0]
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

        confidence_components = self._compute_confidence_components(
            signal_input=signal_input,
            bias_htf=bias_htf,
            internal_mtf_state=internal_mtf_state,
            ltf_trigger_state=ltf_trigger_state,
            cross_frame_aligned=cross_frame_aligned,
        )
        confidence = self._sum_confidence_components(confidence_components)

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
                "candidate_mtf_states": list(candidate_mtf_states),
                "ltf_trigger_state": ltf_trigger_state,
                "candidate_ltf_trigger_states": list(candidate_ltf_trigger_states),
                "market_regime": signal_input.regime.market_regime,
                "sector_regime": signal_input.regime.sector_regime,
                "event_risk_class": signal_input.event_risk.event_risk_class,
                "micro_state": micro_state,
                "micro_trigger_state": micro_trigger_state,
                "micro_present": micro_present,
                "micro_used_for_confirmation": micro_used,
                "cross_frame_aligned": cross_frame_aligned,
                "confidence_components": {
                    key: format(value, "f")
                    for key, value in confidence_components.items()
                },
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
            self.config.htf_timeframe: signal_input.htf,
            self.config.mtf_timeframe: signal_input.mtf,
            self.config.ltf_timeframe: signal_input.ltf,
        }
        for timeframe, frame in frame_expectations.items():
            if frame.timeframe != timeframe:
                raise ValueError(f"Expected {timeframe} frame input.")
            if not frame.structure_history:
                raise ValueError(f"{timeframe} structure history cannot be empty.")
            if frame.structure_history[-1].bar_timestamp != frame.structure.bar_timestamp:
                raise ValueError(f"{timeframe} latest structure must match structure_history[-1].")
        if signal_input.micro is not None:
            if signal_input.micro.timeframe != self.config.micro_timeframe:
                raise ValueError(f"Micro input must use timeframe {self.config.micro_timeframe}.")
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

    def _candidate_internal_mtf_states(self, signal_input: SignalEngineInput) -> list[str]:
        recent_results = signal_input.mtf.structure_history[-self.config.mtf_invalidation_lookback_bars :]
        mtf_zone = signal_input.mtf.zone
        mtf_pattern = signal_input.mtf.pattern

        if (
            mtf_zone.range_status == "NO_VALID_RANGE"
            or mtf_pattern.recontainment.status == "INVALIDATED"
            or self._recent_has_bearish_structure_event(recent_results)
        ):
            return ["INVALIDATED"]
        if mtf_zone.zone_location == "PREMIUM":
            return ["EXTENDED_PREMIUM"]

        candidates: list[str] = []
        if mtf_pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}:
            candidates.append("RECONTAINMENT_CANDIDATE")
        if self._is_discount_response(mtf_zone=mtf_zone, mtf_pattern=mtf_pattern):
            candidates.append("DISCOUNT_RESPONSE")
        if self._is_equilibrium_hold(mtf_zone=mtf_zone, mtf_pattern=mtf_pattern):
            candidates.append("EQUILIBRIUM_HOLD")
        if mtf_pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
            candidates.append("BULLISH_RECLAIM")
        if candidates:
            return candidates
        if signal_input.mtf.structure.trend_state == "MIXED":
            return ["CHOP"]
        return ["NO_STRUCTURE"]

    @staticmethod
    def _is_discount_response(*, mtf_zone, mtf_pattern) -> bool:
        return mtf_zone.zone_location == "DISCOUNT" and (
            mtf_pattern.bullish_fake_breakdown.status in {"NEW_EVENT", "ACTIVE"}
            or mtf_pattern.bullish_reclaim.status in {"CANDIDATE", "NEW_EVENT", "ACTIVE"}
        )

    @staticmethod
    def _is_equilibrium_hold(*, mtf_zone, mtf_pattern) -> bool:
        return mtf_zone.zone_location == "EQUILIBRIUM" and (
            mtf_pattern.compression.status == "COMPRESSED"
            or mtf_pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}
            or mtf_pattern.recontainment.status in {"CANDIDATE", "ACTIVE"}
        )

    def _candidate_trigger_states(
        self,
        frame_input,
        structure_freshness_bars: int,
    ) -> list[LTFTriggerState]:
        candidates: list[LTFTriggerState] = []
        if frame_input.pattern.bullish_trap_reverse.status in {"NEW_EVENT", "ACTIVE"}:
            candidates.append("TRAP_REVERSE_BULLISH")
        if frame_input.pattern.bullish_fake_breakdown.status in {"NEW_EVENT", "ACTIVE"}:
            candidates.append("FAKE_BREAKDOWN_REVERSAL")
        if frame_input.pattern.bullish_reclaim.status in {"NEW_EVENT", "ACTIVE"}:
            candidates.append("LTF_BULLISH_RECLAIM")

        recent_results = frame_input.structure_history[-structure_freshness_bars:]
        if self._recent_has_structure_event(recent_results, "BULLISH_CHOCH"):
            candidates.append("LTF_BULLISH_CHOCH")
        if self._recent_has_structure_event(recent_results, "BULLISH_BOS"):
            candidates.append("LTF_BULLISH_BOS")
        return candidates or ["LTF_NO_TRIGGER"]

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

    def _compute_confidence_components(
        self,
        signal_input: SignalEngineInput,
        bias_htf: SignalBias,
        internal_mtf_state: str,
        ltf_trigger_state: LTFTriggerState,
        cross_frame_aligned: bool,
    ) -> dict[str, Decimal]:
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
        if bias_htf == "BULLISH":
            components["htf_bias"] = self.config.htf_bullish_weight

        mtf_scores = {
            "RECONTAINMENT_CANDIDATE": self.config.mtf_weight_recontainment,
            "BULLISH_RECLAIM": self.config.mtf_weight_reclaim,
            "DISCOUNT_RESPONSE": self.config.mtf_weight_discount,
            "EQUILIBRIUM_HOLD": self.config.mtf_weight_equilibrium,
        }
        components["mtf_state"] = mtf_scores.get(internal_mtf_state, Decimal("0"))

        ltf_scores = {
            "TRAP_REVERSE_BULLISH": self.config.ltf_weight_trap_reverse,
            "FAKE_BREAKDOWN_REVERSAL": self.config.ltf_weight_fake_breakdown,
            "LTF_BULLISH_RECLAIM": self.config.ltf_weight_reclaim,
            "LTF_BULLISH_CHOCH": self.config.ltf_weight_choch,
            "LTF_BULLISH_BOS": self.config.ltf_weight_bos,
        }
        components["ltf_trigger"] = ltf_scores.get(ltf_trigger_state, Decimal("0"))

        if cross_frame_aligned:
            components["cross_frame_alignment"] = self.config.cross_frame_alignment_bonus

        if signal_input.mtf.zone.zone_location == "DISCOUNT":
            components["zone_location"] = self.config.discount_zone_bonus
        elif signal_input.mtf.zone.zone_location == "EQUILIBRIUM":
            components["zone_location"] = self.config.equilibrium_zone_bonus

        if signal_input.mtf.pattern.compression.status == "COMPRESSED":
            components["compression"] = self.config.compression_bonus
        if (
            signal_input.htf.pattern.bullish_displacement.status in {"NEW_EVENT", "ACTIVE"}
            or signal_input.mtf.pattern.bullish_displacement.status in {"NEW_EVENT", "ACTIVE"}
        ):
            components["displacement"] = self.config.displacement_bonus

        if signal_input.regime.allows_longs is True:
            if (
                signal_input.regime.market_permission_score is not None
                and signal_input.regime.market_permission_score >= self.config.regime_market_permission_strong_threshold
                and signal_input.regime.sector_permission_score is not None
                and signal_input.regime.sector_permission_score >= self.config.regime_sector_permission_strong_threshold
            ):
                components["regime_permission"] = self.config.regime_permission_strong_bonus
            else:
                components["regime_permission"] = self.config.regime_permission_supportive_bonus

        sector_scores = {
            "STRONG": self.config.sector_strength_bonus_strong,
            "NEUTRAL": self.config.sector_strength_bonus_neutral,
            "WEAK": self.config.sector_strength_bonus_weak,
            "UNKNOWN": self.config.sector_strength_bonus_unknown,
        }
        components["sector_strength"] = sector_scores[signal_input.sector_context.sector_strength]
        components["event_risk_penalty"] = -min(
            self.config.max_event_risk_soft_penalty,
            signal_input.event_risk.soft_penalty,
        )
        return components

    @staticmethod
    def _sum_confidence_components(components: dict[str, Decimal]) -> Decimal:
        score = sum(components.values(), Decimal("0"))
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
