from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from doctrine_engine.engines.models import (
    SignalEngineInput,
    StructureEngineResult,
    TradePlanEngineInput,
    TradePlanEngineResult,
)


@dataclass(frozen=True, slots=True)
class TradePlanEngine:
    def build_plan(self, trade_plan_input: TradePlanEngineInput) -> TradePlanEngineResult:
        self._validate_input(trade_plan_input)

        signal_result = trade_plan_input.signal_result
        signal_source = trade_plan_input.signal_source
        setup_state = signal_result.setup_state
        ltf_trigger_state = self._require_context_value(signal_result.extensible_context, "ltf_trigger_state")

        entry_type = self._determine_entry_type(setup_state, ltf_trigger_state)
        entry_origin = self._entry_origin(setup_state)
        entry_zone_low, entry_zone_high = self._entry_zone(setup_state, signal_source)
        confirmation_level = self._confirmation_level(
            entry_type=entry_type,
            setup_state=setup_state,
            signal_source=signal_source,
            entry_zone_high=entry_zone_high,
        )
        invalidation_level, invalidation_anchor_type = self._invalidation_level(
            setup_state=setup_state,
            signal_source=signal_source,
            entry_zone_low=entry_zone_low,
        )
        tp1, tp1_anchor_type = self._tp1(
            setup_state=setup_state,
            signal_source=signal_source,
            confirmation_level=confirmation_level,
        )
        tp2, tp2_anchor_type = self._tp2(
            signal_source=signal_source,
            tp1=tp1,
        )

        return TradePlanEngineResult(
            signal_id=trade_plan_input.signal_id,
            symbol_id=signal_result.symbol_id,
            ticker=signal_result.ticker,
            plan_timestamp=signal_result.signal_timestamp,
            known_at=signal_result.known_at,
            entry_type=entry_type,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            confirmation_level=confirmation_level,
            invalidation_level=invalidation_level,
            tp1=tp1,
            tp2=tp2,
            trail_mode="STRUCTURAL",
            plan_reason_codes=[
                self._entry_reason_code(entry_type, entry_origin),
                self._invalidation_reason_code(invalidation_anchor_type),
                self._tp1_reason_code(tp1_anchor_type),
                self._tp2_reason_code(tp2_anchor_type),
                "TRAIL_STRUCTURAL",
            ],
            extensible_context={
                "source_setup_state": setup_state,
                "source_ltf_trigger_state": ltf_trigger_state,
                "entry_origin": entry_origin,
                "invalidation_anchor_type": invalidation_anchor_type,
                "tp1_anchor_type": tp1_anchor_type,
                "tp2_anchor_type": tp2_anchor_type,
            },
        )

    def _validate_input(self, trade_plan_input: TradePlanEngineInput) -> None:
        signal_result = trade_plan_input.signal_result
        signal_source = trade_plan_input.signal_source

        if signal_result.signal != "LONG":
            raise ValueError("Trade plans require a LONG signal.")
        if signal_result.symbol_id != signal_source.symbol_id:
            raise ValueError("Signal result and source symbol_id must match.")
        if signal_result.ticker != signal_source.ticker:
            raise ValueError("Signal result and source ticker must match.")
        if signal_result.htf_bar_timestamp != signal_source.htf.latest_bar.bar_timestamp:
            raise ValueError("HTF timestamps must match.")
        if signal_result.mtf_bar_timestamp != signal_source.mtf.latest_bar.bar_timestamp:
            raise ValueError("MTF timestamps must match.")
        if signal_result.ltf_bar_timestamp != signal_source.ltf.latest_bar.bar_timestamp:
            raise ValueError("LTF timestamps must match.")

    def _determine_entry_type(self, setup_state: str, ltf_trigger_state: str) -> str:
        if setup_state == "BULLISH_RECLAIM" or ltf_trigger_state in {
            "TRAP_REVERSE_BULLISH",
            "FAKE_BREAKDOWN_REVERSAL",
            "LTF_BULLISH_RECLAIM",
        }:
            return "AGGRESSIVE"
        if ltf_trigger_state in {"LTF_BULLISH_CHOCH", "LTF_BULLISH_BOS"}:
            return "CONFIRMATION"
        if setup_state in {
            "RECONTAINMENT_CONFIRMED",
            "DISCOUNT_RESPONSE",
            "EQUILIBRIUM_HOLD",
        }:
            return "BASE"
        raise ValueError("Unable to determine trade-plan entry type.")

    def _entry_origin(self, setup_state: str) -> str:
        return {
            "RECONTAINMENT_CONFIRMED": "RECONTAINMENT",
            "DISCOUNT_RESPONSE": "DISCOUNT",
            "EQUILIBRIUM_HOLD": "EQUILIBRIUM",
            "BULLISH_RECLAIM": "RECLAIM",
        }.get(setup_state, "UNKNOWN")

    def _entry_zone(self, setup_state: str, signal_source: SignalEngineInput) -> tuple[Decimal, Decimal]:
        mtf_low = signal_source.mtf.zone.active_swing_low
        mtf_eq = signal_source.mtf.zone.equilibrium
        mtf_eq_low = signal_source.mtf.zone.equilibrium_band_low
        mtf_eq_high = signal_source.mtf.zone.equilibrium_band_high
        support_ref = self._support_ref(signal_source)

        if setup_state == "RECONTAINMENT_CONFIRMED":
            if mtf_low is None or mtf_eq is None:
                raise ValueError("Recontainment plan requires MTF low and equilibrium.")
            entry_zone_low = max(mtf_low, support_ref) if support_ref is not None else mtf_low
            entry_zone_high = mtf_eq
        elif setup_state == "DISCOUNT_RESPONSE":
            if mtf_low is None or mtf_eq_low is None:
                raise ValueError("Discount-response plan requires MTF low and equilibrium band low.")
            entry_zone_low = mtf_low
            entry_zone_high = mtf_eq_low
        elif setup_state == "EQUILIBRIUM_HOLD":
            if mtf_eq_low is None or mtf_eq_high is None:
                raise ValueError("Equilibrium-hold plan requires MTF equilibrium band.")
            entry_zone_low = mtf_eq_low
            entry_zone_high = mtf_eq_high
        elif setup_state == "BULLISH_RECLAIM":
            support_ref = self._reclaim_support_ref(signal_source)
            if support_ref is None:
                raise ValueError("Bullish reclaim plan requires a support reference.")
            if mtf_eq_low is None:
                raise ValueError("Bullish reclaim plan requires MTF equilibrium band low.")
            entry_zone_low = support_ref
            entry_zone_high = max(support_ref, mtf_eq_low)
        else:
            raise ValueError("Unsupported setup_state for trade plan.")

        if entry_zone_high < entry_zone_low:
            entry_zone_high = entry_zone_low
        return entry_zone_low, entry_zone_high

    def _support_ref(self, signal_source: SignalEngineInput) -> Decimal | None:
        return self._first_non_null(
            signal_source.ltf.pattern.bullish_reclaim.reference_price,
            signal_source.ltf.pattern.bullish_fake_breakdown.reference_price,
            signal_source.ltf.pattern.bullish_trap_reverse.reference_price,
            signal_source.ltf.zone.active_swing_low,
            signal_source.mtf.zone.active_swing_low,
        )

    def _reclaim_support_ref(self, signal_source: SignalEngineInput) -> Decimal | None:
        return self._first_non_null(
            signal_source.ltf.pattern.bullish_fake_breakdown.reference_price,
            signal_source.ltf.pattern.bullish_trap_reverse.reference_price,
            signal_source.ltf.zone.active_swing_low,
            signal_source.mtf.zone.active_swing_low,
            signal_source.ltf.pattern.bullish_reclaim.reference_price,
        )

    def _confirmation_level(
        self,
        *,
        entry_type: str,
        setup_state: str,
        signal_source: SignalEngineInput,
        entry_zone_high: Decimal,
    ) -> Decimal:
        if entry_type == "CONFIRMATION":
            choch_ref = self._freshest_bullish_break_reference(signal_source.ltf.structure_history, "BULLISH_CHOCH", entry_zone_high)
            if choch_ref is not None:
                return choch_ref
            bos_ref = self._freshest_bullish_break_reference(signal_source.ltf.structure_history, "BULLISH_BOS", entry_zone_high)
            if bos_ref is not None:
                return bos_ref
            raise ValueError("Confirmation entry requires a bullish trigger reference above the zone.")

        candidates: list[Decimal] = []
        if setup_state in {"DISCOUNT_RESPONSE", "RECONTAINMENT_CONFIRMED", "BULLISH_RECLAIM"}:
            mtf_eq = signal_source.mtf.zone.equilibrium
            if mtf_eq is not None and mtf_eq > entry_zone_high:
                candidates.append(mtf_eq)

        freshest_break = self._freshest_bullish_break_reference(signal_source.ltf.structure_history, None, entry_zone_high)
        if freshest_break is not None:
            candidates.append(freshest_break)

        mtf_high = signal_source.mtf.zone.active_swing_high
        if mtf_high is not None and mtf_high > entry_zone_high:
            candidates.append(mtf_high)

        if not candidates:
            raise ValueError("No structural confirmation level exists above the entry zone.")
        return min(candidates)

    def _freshest_bullish_break_reference(
        self,
        structure_history: list[StructureEngineResult],
        event_type: str | None,
        threshold: Decimal,
    ) -> Decimal | None:
        matching_events = []
        for result in reversed(structure_history):
            for event in reversed(result.events_on_bar):
                if event.event_type not in {"BULLISH_CHOCH", "BULLISH_BOS"}:
                    continue
                if event_type is not None and event.event_type != event_type:
                    continue
                if event.reference_price > threshold:
                    matching_events.append(event)
            if matching_events:
                break
        if not matching_events:
            return None
        return matching_events[0].reference_price

    def _invalidation_level(
        self,
        *,
        setup_state: str,
        signal_source: SignalEngineInput,
        entry_zone_low: Decimal,
    ) -> tuple[Decimal, str]:
        if setup_state == "BULLISH_RECLAIM":
            candidates = [
                ("RECLAIM_REFERENCE", signal_source.ltf.pattern.bullish_reclaim.reference_price),
                ("FAKE_BREAKDOWN_REFERENCE", signal_source.ltf.pattern.bullish_fake_breakdown.reference_price),
                ("LTF_STRUCTURAL_LOW", signal_source.ltf.zone.active_swing_low),
                ("MTF_STRUCTURAL_LOW", signal_source.mtf.zone.active_swing_low),
            ]
        elif setup_state == "RECONTAINMENT_CONFIRMED":
            candidates = [
                ("RECONTAINMENT_RANGE_LOW", signal_source.mtf.pattern.recontainment.active_range_low),
                ("MTF_STRUCTURAL_LOW", signal_source.mtf.zone.active_swing_low),
                ("LTF_STRUCTURAL_LOW", signal_source.ltf.zone.active_swing_low),
            ]
        elif setup_state == "DISCOUNT_RESPONSE":
            candidates = [
                ("MTF_STRUCTURAL_LOW", signal_source.mtf.zone.active_swing_low),
                ("LTF_STRUCTURAL_LOW", signal_source.ltf.zone.active_swing_low),
            ]
        elif setup_state == "EQUILIBRIUM_HOLD":
            candidates = [
                ("LTF_STRUCTURAL_LOW", signal_source.ltf.zone.active_swing_low),
                ("MTF_STRUCTURAL_LOW", signal_source.mtf.zone.active_swing_low),
            ]
        else:
            raise ValueError("Unsupported setup_state for invalidation.")

        for anchor_type, value in candidates:
            if value is None:
                continue
            if value >= entry_zone_low:
                raise ValueError("Invalidation anchor cannot fall inside the entry zone.")
            return value, anchor_type
        raise ValueError("No structural invalidation anchor exists.")

    def _tp1(
        self,
        *,
        setup_state: str,
        signal_source: SignalEngineInput,
        confirmation_level: Decimal,
    ) -> tuple[Decimal, str]:
        candidates: list[tuple[Decimal, str]] = []

        if setup_state in {"DISCOUNT_RESPONSE", "RECONTAINMENT_CONFIRMED", "BULLISH_RECLAIM"}:
            mtf_eq = signal_source.mtf.zone.equilibrium
            if mtf_eq is not None and mtf_eq > confirmation_level:
                candidates.append((mtf_eq, "MTF_EQUILIBRIUM"))

        for swing in signal_source.ltf.structure.swing_points:
            if swing.kind == "HIGH" and swing.price > confirmation_level:
                candidates.append((swing.price, "LTF_SWING_HIGH"))

        ltf_high = signal_source.ltf.zone.active_swing_high
        if ltf_high is not None and ltf_high > confirmation_level:
            candidates.append((ltf_high, "LTF_ACTIVE_SWING_HIGH"))

        mtf_high = signal_source.mtf.zone.active_swing_high
        if mtf_high is not None and mtf_high > confirmation_level:
            candidates.append((mtf_high, "MTF_ACTIVE_SWING_HIGH"))

        if setup_state == "EQUILIBRIUM_HOLD":
            candidates = [candidate for candidate in candidates if candidate[1] != "MTF_EQUILIBRIUM"]

        if not candidates:
            raise ValueError("No structural TP1 candidate exists.")

        return min(candidates, key=lambda item: item[0])

    def _tp2(
        self,
        *,
        signal_source: SignalEngineInput,
        tp1: Decimal,
    ) -> tuple[Decimal, str]:
        candidates: list[tuple[Decimal, str]] = []

        htf_high = signal_source.htf.zone.active_swing_high
        if htf_high is not None and htf_high > tp1 and htf_high != tp1:
            candidates.append((htf_high, "HTF_ACTIVE_SWING_HIGH"))

        for swing in signal_source.htf.structure.swing_points:
            if swing.kind == "HIGH" and swing.price > tp1 and swing.price != tp1:
                candidates.append((swing.price, "HTF_SWING_HIGH"))

        mtf_high = signal_source.mtf.zone.active_swing_high
        if mtf_high is not None and mtf_high > tp1 and mtf_high != tp1:
            candidates.append((mtf_high, "MTF_ACTIVE_SWING_HIGH"))

        if not candidates:
            raise ValueError("No structural TP2 candidate exists.")

        return min(candidates, key=lambda item: item[0])

    def _entry_reason_code(self, entry_type: str, entry_origin: str) -> str:
        if entry_type == "CONFIRMATION":
            return "ENTRY_FROM_CONFIRMATION_BREAK"
        return {
            "RECONTAINMENT": "ENTRY_FROM_RECONTAINMENT",
            "DISCOUNT": "ENTRY_FROM_DISCOUNT",
            "EQUILIBRIUM": "ENTRY_FROM_EQUILIBRIUM",
            "RECLAIM": "ENTRY_FROM_RECLAIM",
        }[entry_origin]

    def _invalidation_reason_code(self, invalidation_anchor_type: str) -> str:
        if invalidation_anchor_type == "RECLAIM_REFERENCE":
            return "INVALIDATION_BELOW_RECLAIM_FAILURE"
        if invalidation_anchor_type == "RECONTAINMENT_RANGE_LOW":
            return "INVALIDATION_BELOW_RECONTAINMENT_RANGE"
        return "INVALIDATION_BELOW_STRUCTURAL_LOW"

    def _tp1_reason_code(self, tp1_anchor_type: str) -> str:
        if tp1_anchor_type == "MTF_EQUILIBRIUM":
            return "TP1_AT_EQUILIBRIUM_RETURN"
        return "TP1_AT_INTERNAL_LIQUIDITY"

    def _tp2_reason_code(self, tp2_anchor_type: str) -> str:
        if tp2_anchor_type in {"HTF_ACTIVE_SWING_HIGH", "HTF_SWING_HIGH"}:
            return "TP2_AT_HTF_OBJECTIVE"
        return "TP2_AT_EXTERNAL_LIQUIDITY"

    def _first_non_null(self, *values: Decimal | None) -> Decimal | None:
        for value in values:
            if value is not None:
                return value
        return None

    def _require_context_value(self, extensible_context: dict[str, object], key: str) -> str:
        value = extensible_context.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Signal result extensible_context must contain string {key}.")
        return value
