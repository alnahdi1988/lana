from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from doctrine_engine.engines.models import (
    ActiveFlag,
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    PatternEvent,
    RecontainmentResult,
    StructureEngineResult,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.structure_engine import StructureEngine
from doctrine_engine.engines.zone_engine import ZoneEngine


@dataclass(frozen=True, slots=True)
class PatternEngineConfig:
    atr_period: int = 20
    config_version: str = "v1"
    compression_lookback_bars: int = 5
    compression_range_ratio: Decimal = Decimal("0.75")
    compression_realized_range_atr_multiple: Decimal = Decimal("2.5")
    compression_near_equilibrium_ratio: Decimal = Decimal("0.15")
    displacement_atr_multiple: Decimal = Decimal("1.5")
    displacement_close_location_ratio: Decimal = Decimal("0.75")
    displacement_sequence_length: int = 3
    displacement_active_bars: int = 3
    displacement_cooldown_bars: int = 3
    reclaim_reentry_window_bars: int = 2
    reclaim_dedup_bars: int = 5
    fake_breakdown_max_extension_atr: Decimal = Decimal("0.50")
    fake_breakdown_active_bars: int = 3
    fake_breakdown_reentry_window_bars: int = 2
    fake_breakdown_dedup_bars: int = 5
    trap_reverse_lookback_bars: int = 5
    trap_reverse_active_bars: int = 5
    recontainment_lookback_bars: int = 10
    recontainment_max_extension_atr: Decimal = Decimal("0.25")


@dataclass(slots=True)
class _DisplacementRecord:
    bar_index: int
    event_timestamp: object
    reference_timestamp: object
    reference_price: Decimal
    event_high: Decimal
    mode: str
    range_multiple_atr: Decimal
    close_location_ratio: Decimal


@dataclass(slots=True)
class _ReferenceCandidate:
    reference_price: Decimal
    reference_timestamp: object
    start_index: int
    start_timestamp: object
    sweep_low: Decimal
    reentry_index: int | None = None


@dataclass(slots=True)
class _ReferenceEvent:
    reference_price: Decimal
    reference_timestamp: object
    event_index: int
    event_timestamp: object
    active_until: int | None = None


@dataclass(slots=True)
class _RecontainmentState:
    status: str = "NONE"
    source_displacement: _DisplacementRecord | None = None
    candidate_start_index: int | None = None
    candidate_start_timestamp: object | None = None


class PatternEngine:
    EVENT_ORDER = {
        "BULLISH_DISPLACEMENT": 0,
        "BULLISH_RECLAIM": 1,
        "BULLISH_FAKE_BREAKDOWN": 2,
        "BULLISH_TRAP_REVERSE": 3,
        "RECONTAINMENT_ENTERED": 4,
        "RECONTAINMENT_INVALIDATED": 5,
    }

    def __init__(
        self,
        config: PatternEngineConfig | None = None,
        structure_engine: StructureEngine | None = None,
        zone_engine: ZoneEngine | None = None,
    ) -> None:
        self.config = config or PatternEngineConfig()
        self.structure_engine = structure_engine or StructureEngine()
        self.zone_engine = zone_engine or ZoneEngine()

    def evaluate(
        self,
        bars: Sequence[EngineBar],
        structure_history: Sequence[StructureEngineResult] | None = None,
        zone_history: Sequence[ZoneEngineResult] | None = None,
    ) -> PatternEngineResult:
        return self.evaluate_history(bars, structure_history=structure_history, zone_history=zone_history)[-1]

    def evaluate_history(
        self,
        bars: Sequence[EngineBar],
        structure_history: Sequence[StructureEngineResult] | None = None,
        zone_history: Sequence[ZoneEngineResult] | None = None,
    ) -> list[PatternEngineResult]:
        ordered_bars = self._validate_bars(bars)
        structure_results = list(structure_history) if structure_history is not None else self.structure_engine.evaluate_history(ordered_bars)
        zone_results = list(zone_history) if zone_history is not None else self.zone_engine.evaluate_history(ordered_bars, structure_results)
        if len(structure_results) != len(ordered_bars) or len(zone_results) != len(ordered_bars):
            raise ValueError("PatternEngine requires structure and zone histories aligned to bars.")

        atr_values = self._compute_atr_values(ordered_bars)
        displacement_history: list[_DisplacementRecord] = []
        last_displacement_index_by_reference: dict[object, int] = {}
        active_displacement: _DisplacementRecord | None = None
        active_displacement_until: int | None = None

        reclaim_candidate: _ReferenceCandidate | None = None
        reclaim_active: _ReferenceEvent | None = None
        reclaim_history: list[_ReferenceEvent] = []
        last_reclaim_event_index_by_reference: dict[object, int] = {}

        fake_candidate: _ReferenceCandidate | None = None
        fake_active: _ReferenceEvent | None = None
        fake_history: list[_ReferenceEvent] = []
        last_fake_event_index_by_reference: dict[object, int] = {}

        trap_active: _ReferenceEvent | None = None
        trap_trigger: str | None = None
        last_trap_event_index_by_key: dict[tuple[object, str], int] = {}

        recontainment_state = _RecontainmentState()
        results: list[PatternEngineResult] = []

        for index, (bar, structure_result, zone_result) in enumerate(zip(ordered_bars, structure_results, zone_results)):
            atr_value = atr_values[index]
            events_on_bar: list[PatternEvent] = []

            compression = self._evaluate_compression(
                bars=ordered_bars,
                index=index,
                atr_value=atr_value,
                structure_result=structure_result,
                zone_result=zone_result,
            )

            displacement = DisplacementResult(
                status="NONE",
                mode=None,
                event_timestamp=None,
                reference_price=None,
                reference_timestamp=None,
                range_multiple_atr=None,
                close_location_ratio=None,
            )

            if atr_value is not None:
                displacement, emitted_displacement = self._advance_displacement(
                    bars=ordered_bars,
                    index=index,
                    atr_value=atr_value,
                    structure_result=structure_result,
                    active_displacement=active_displacement,
                    active_displacement_until=active_displacement_until,
                    last_event_index_by_reference=last_displacement_index_by_reference,
                )
                if emitted_displacement is not None:
                    active_displacement = emitted_displacement
                    active_displacement_until = index + self.config.displacement_active_bars
                    displacement_history.append(emitted_displacement)
                    last_displacement_index_by_reference[emitted_displacement.reference_timestamp] = index
                    events_on_bar.append(
                        PatternEvent(
                            event_type="BULLISH_DISPLACEMENT",
                            event_timestamp=bar.bar_timestamp,
                            reference_timestamp=emitted_displacement.reference_timestamp,
                            reference_price=emitted_displacement.reference_price,
                        )
                    )
                elif active_displacement is not None and active_displacement_until is not None and index <= active_displacement_until:
                    displacement = DisplacementResult(
                        status="ACTIVE",
                        mode=active_displacement.mode,
                        event_timestamp=active_displacement.event_timestamp,
                        reference_price=active_displacement.reference_price,
                        reference_timestamp=active_displacement.reference_timestamp,
                        range_multiple_atr=active_displacement.range_multiple_atr,
                        close_location_ratio=active_displacement.close_location_ratio,
                    )
                else:
                    active_displacement = None
                    active_displacement_until = None

            reclaim, reclaim_candidate, reclaim_active, reclaim_emitted = self._advance_reclaim(
                bar=bar,
                index=index,
                structure_result=structure_result,
                zone_result=zone_result,
                candidate=reclaim_candidate,
                active_event=reclaim_active,
                last_event_index_by_reference=last_reclaim_event_index_by_reference,
            )
            if reclaim_emitted is not None:
                reclaim_history.append(reclaim_emitted)
                last_reclaim_event_index_by_reference[reclaim_emitted.reference_timestamp] = index
                events_on_bar.append(
                    PatternEvent(
                        event_type="BULLISH_RECLAIM",
                        event_timestamp=bar.bar_timestamp,
                        reference_timestamp=reclaim_emitted.reference_timestamp,
                        reference_price=reclaim_emitted.reference_price,
                    )
                )

            fake_breakdown = LifecyclePatternResult(
                status="NONE",
                reference_price=None,
                reference_timestamp=None,
                sweep_low=None,
                candidate_start_timestamp=None,
                event_timestamp=None,
            )
            if atr_value is not None:
                fake_breakdown, fake_candidate, fake_active, fake_emitted = self._advance_fake_breakdown(
                    bar=bar,
                    index=index,
                    atr_value=atr_value,
                    structure_result=structure_result,
                    zone_result=zone_result,
                    candidate=fake_candidate,
                    active_event=fake_active,
                    last_event_index_by_reference=last_fake_event_index_by_reference,
                )
                if fake_emitted is not None:
                    fake_history.append(fake_emitted)
                    last_fake_event_index_by_reference[fake_emitted.reference_timestamp] = index
                    events_on_bar.append(
                        PatternEvent(
                            event_type="BULLISH_FAKE_BREAKDOWN",
                            event_timestamp=bar.bar_timestamp,
                            reference_timestamp=fake_emitted.reference_timestamp,
                            reference_price=fake_emitted.reference_price,
                        )
                    )

            trap_reverse, trap_active, trap_trigger, trap_emitted = self._advance_trap_reverse(
                bar=bar,
                index=index,
                structure_history=structure_results,
                zone_result=zone_result,
                fake_history=fake_history,
                reclaim_history=reclaim_history,
                active_event=trap_active,
                active_trigger=trap_trigger,
                last_event_index_by_key=last_trap_event_index_by_key,
            )
            if trap_emitted is not None and trap_trigger is not None:
                last_trap_event_index_by_key[(trap_emitted.reference_timestamp, trap_trigger)] = index
                events_on_bar.append(
                    PatternEvent(
                        event_type="BULLISH_TRAP_REVERSE",
                        event_timestamp=bar.bar_timestamp,
                        reference_timestamp=trap_emitted.reference_timestamp,
                        reference_price=trap_emitted.reference_price,
                    )
                )

            recontainment, recontainment_state, recontainment_event_type = self._advance_recontainment(
                bars=ordered_bars,
                index=index,
                atr_value=atr_value,
                structure_history=structure_results,
                zone_result=zone_result,
                displacement_history=displacement_history,
                current_state=recontainment_state,
            )
            if recontainment_event_type is not None:
                events_on_bar.append(
                    PatternEvent(
                        event_type=recontainment_event_type,
                        event_timestamp=bar.bar_timestamp,
                        reference_timestamp=(
                            recontainment.source_displacement_timestamp
                            if recontainment_event_type == "RECONTAINMENT_ENTERED"
                            else None
                        ),
                        reference_price=recontainment.source_displacement_reference_price,
                    )
                )

            ordered_events = sorted(events_on_bar, key=lambda event: self.EVENT_ORDER[event.event_type])
            results.append(
                PatternEngineResult(
                    symbol_id=bar.symbol_id,
                    timeframe=bar.timeframe,
                    bar_timestamp=bar.bar_timestamp,
                    known_at=bar.known_at,
                    config_version=self.config.config_version,
                    compression=compression,
                    bullish_displacement=displacement,
                    bullish_reclaim=reclaim,
                    bullish_fake_breakdown=fake_breakdown,
                    bullish_trap_reverse=trap_reverse,
                    recontainment=recontainment,
                    events_on_bar=ordered_events,
                    active_flags=self._build_active_flags(
                        compression=compression,
                        displacement=displacement,
                        reclaim=reclaim,
                        fake_breakdown=fake_breakdown,
                        trap_reverse=trap_reverse,
                        recontainment=recontainment,
                    ),
                )
            )

        return results

    def _validate_bars(self, bars: Sequence[EngineBar]) -> list[EngineBar]:
        if not bars:
            raise ValueError("PatternEngine requires at least one bar.")

        ordered = sorted(bars, key=lambda bar: bar.bar_timestamp)
        first = ordered[0]
        for bar in ordered[1:]:
            if bar.symbol_id != first.symbol_id:
                raise ValueError("All bars must share the same symbol_id.")
            if bar.timeframe != first.timeframe:
                raise ValueError("All bars must share the same timeframe.")
        return ordered

    def _compute_atr_values(self, bars: Sequence[EngineBar]) -> list[Decimal | None]:
        true_ranges: list[Decimal | None] = [None]
        for index in range(1, len(bars)):
            current_bar = bars[index]
            previous_close = bars[index - 1].close_price
            true_ranges.append(
                max(
                    current_bar.high_price - current_bar.low_price,
                    abs(current_bar.high_price - previous_close),
                    abs(current_bar.low_price - previous_close),
                )
            )

        atr_values: list[Decimal | None] = []
        for index in range(len(bars)):
            window = [
                value
                for value in true_ranges[max(1, index - self.config.atr_period + 1) : index + 1]
                if value is not None
            ]
            if len(window) < self.config.atr_period:
                atr_values.append(None)
                continue
            atr_values.append(sum(window, Decimal("0")) / Decimal(str(self.config.atr_period)))
        return atr_values

    def _evaluate_compression(
        self,
        bars: Sequence[EngineBar],
        index: int,
        atr_value: Decimal | None,
        structure_result: StructureEngineResult,
        zone_result: ZoneEngineResult,
    ) -> CompressionResult:
        if atr_value is None:
            return CompressionResult(status="NOT_COMPRESSED", criteria_met=[], lookback_bars=self.config.compression_lookback_bars)

        criteria_met: list[str] = []
        lookback = self.config.compression_lookback_bars
        lookback_bars = bars[max(0, index - lookback + 1) : index + 1]

        if len(lookback_bars) == lookback:
            average_range = sum(
                (bar.high_price - bar.low_price for bar in lookback_bars),
                Decimal("0"),
            ) / Decimal(str(lookback))
            if average_range < self.config.compression_range_ratio * atr_value:
                criteria_met.append("RANGE_VS_ATR")

            realized_range = max(bar.high_price for bar in lookback_bars) - min(bar.low_price for bar in lookback_bars)
            if realized_range < self.config.compression_realized_range_atr_multiple * atr_value:
                criteria_met.append("REALIZED_RANGE_VS_ATR")

        if len(structure_result.swing_points) >= 4:
            first, second, third, fourth = structure_result.swing_points[-4:]
            if abs(fourth.price - third.price) < abs(second.price - first.price):
                criteria_met.append("LEG_CONTRACTION")

        if zone_result.range_status == "RANGE_AVAILABLE":
            if abs(bars[index].close_price - zone_result.equilibrium) <= (
                self.config.compression_near_equilibrium_ratio * zone_result.range_width
            ):
                criteria_met.append("NEAR_EQUILIBRIUM")

        status = "COMPRESSED" if len(criteria_met) >= 3 else "NOT_COMPRESSED"
        return CompressionResult(status=status, criteria_met=criteria_met, lookback_bars=lookback)

    def _advance_displacement(
        self,
        bars: Sequence[EngineBar],
        index: int,
        atr_value: Decimal,
        structure_result: StructureEngineResult,
        active_displacement: _DisplacementRecord | None,
        active_displacement_until: int | None,
        last_event_index_by_reference: dict[object, int],
    ) -> tuple[DisplacementResult, _DisplacementRecord | None]:
        reference_price = structure_result.reference_levels.bullish_bos_reference_price
        reference_timestamp = structure_result.reference_levels.bullish_bos_reference_timestamp
        if reference_price is None or reference_timestamp is None:
            return (
                DisplacementResult(
                    status="ACTIVE" if active_displacement and active_displacement_until is not None and index <= active_displacement_until else "NONE",
                    mode=active_displacement.mode if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                    event_timestamp=active_displacement.event_timestamp if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                    reference_price=active_displacement.reference_price if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                    reference_timestamp=active_displacement.reference_timestamp if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                    range_multiple_atr=active_displacement.range_multiple_atr if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                    close_location_ratio=active_displacement.close_location_ratio if active_displacement and active_displacement_until is not None and index <= active_displacement_until else None,
                ),
                None,
            )

        bar = bars[index]
        bar_range = bar.high_price - bar.low_price
        single_close_location = (bar.close_price - bar.low_price) / bar_range if bar_range != 0 else Decimal("0")
        single_bar_qualifies = (
            bar_range > self.config.displacement_atr_multiple * atr_value
            and bar.close_price > reference_price
            and single_close_location >= self.config.displacement_close_location_ratio
        )

        sequence_qualifies = False
        sequence_close_location = Decimal("0")
        sequence_range_multiple = Decimal("0")
        if index + 1 >= self.config.displacement_sequence_length:
            window = bars[index - self.config.displacement_sequence_length + 1 : index + 1]
            window_high = max(window_bar.high_price for window_bar in window)
            window_low = min(window_bar.low_price for window_bar in window)
            window_range = window_high - window_low
            sequence_close_location = (bar.close_price - window_low) / window_range if window_range != 0 else Decimal("0")
            sequence_range_multiple = window_range / atr_value if atr_value != 0 else Decimal("0")
            sequence_qualifies = (
                window_range > self.config.displacement_atr_multiple * atr_value
                and bar.close_price > reference_price
                and sequence_close_location >= self.config.displacement_close_location_ratio
            )

        if not single_bar_qualifies and not sequence_qualifies:
            if active_displacement and active_displacement_until is not None and index <= active_displacement_until:
                return (
                    DisplacementResult(
                        status="ACTIVE",
                        mode=active_displacement.mode,
                        event_timestamp=active_displacement.event_timestamp,
                        reference_price=active_displacement.reference_price,
                        reference_timestamp=active_displacement.reference_timestamp,
                        range_multiple_atr=active_displacement.range_multiple_atr,
                        close_location_ratio=active_displacement.close_location_ratio,
                    ),
                    None,
                )
            return (
                DisplacementResult(
                    status="NONE",
                    mode=None,
                    event_timestamp=None,
                    reference_price=None,
                    reference_timestamp=None,
                    range_multiple_atr=None,
                    close_location_ratio=None,
                ),
                None,
            )

        last_event_index = last_event_index_by_reference.get(reference_timestamp)
        if last_event_index is not None and (index - last_event_index) <= self.config.displacement_cooldown_bars:
            if active_displacement and active_displacement_until is not None and index <= active_displacement_until:
                return (
                    DisplacementResult(
                        status="ACTIVE",
                        mode=active_displacement.mode,
                        event_timestamp=active_displacement.event_timestamp,
                        reference_price=active_displacement.reference_price,
                        reference_timestamp=active_displacement.reference_timestamp,
                        range_multiple_atr=active_displacement.range_multiple_atr,
                        close_location_ratio=active_displacement.close_location_ratio,
                    ),
                    None,
                )
            return (
                DisplacementResult(
                    status="NONE",
                    mode=None,
                    event_timestamp=None,
                    reference_price=None,
                    reference_timestamp=None,
                    range_multiple_atr=None,
                    close_location_ratio=None,
                ),
                None,
            )

        mode = "SINGLE_BAR" if single_bar_qualifies else "SEQUENCE"
        range_multiple = bar_range / atr_value if mode == "SINGLE_BAR" and atr_value != 0 else sequence_range_multiple
        close_location_ratio = single_close_location if mode == "SINGLE_BAR" else sequence_close_location
        record = _DisplacementRecord(
            bar_index=index,
            event_timestamp=bar.bar_timestamp,
            reference_timestamp=reference_timestamp,
            reference_price=reference_price,
            event_high=bar.high_price,
            mode=mode,
            range_multiple_atr=range_multiple,
            close_location_ratio=close_location_ratio,
        )
        return (
            DisplacementResult(
                status="NEW_EVENT",
                mode=mode,
                event_timestamp=bar.bar_timestamp,
                reference_price=reference_price,
                reference_timestamp=reference_timestamp,
                range_multiple_atr=range_multiple,
                close_location_ratio=close_location_ratio,
            ),
            record,
        )

    def _advance_reclaim(
        self,
        bar: EngineBar,
        index: int,
        structure_result: StructureEngineResult,
        zone_result: ZoneEngineResult,
        candidate: _ReferenceCandidate | None,
        active_event: _ReferenceEvent | None,
        last_event_index_by_reference: dict[object, int],
    ) -> tuple[LifecyclePatternResult, _ReferenceCandidate | None, _ReferenceEvent | None, _ReferenceEvent | None]:
        emitted_event: _ReferenceEvent | None = None
        status = "NONE"
        reference_price, reference_timestamp = self._support_reference(structure_result, zone_result)

        if active_event is not None:
            if bar.close_price < active_event.reference_price:
                status = "INVALIDATED"
                active_event = None
            else:
                status = "ACTIVE"

        if candidate is not None:
            candidate.sweep_low = min(candidate.sweep_low, bar.low_price)
            if candidate.reentry_index is None:
                if bar.close_price > candidate.reference_price and (index - candidate.start_index) <= self.config.reclaim_reentry_window_bars:
                    candidate.reentry_index = index
                elif (index - candidate.start_index) > self.config.reclaim_reentry_window_bars:
                    status = "INVALIDATED"
                    candidate = None
            else:
                if index == candidate.reentry_index + 1 and bar.close_price >= candidate.reference_price:
                    emitted_event = _ReferenceEvent(
                        reference_price=candidate.reference_price,
                        reference_timestamp=candidate.reference_timestamp,
                        event_index=index,
                        event_timestamp=bar.bar_timestamp,
                    )
                    active_event = emitted_event
                    candidate = None
                    status = "NEW_EVENT"
                elif index > candidate.reentry_index + 1:
                    status = "INVALIDATED"
                    candidate = None

        if active_event is None and candidate is None and reference_price is not None and reference_timestamp is not None:
            last_event_index = last_event_index_by_reference.get(reference_timestamp)
            if (
                bar.low_price < reference_price
                and (last_event_index is None or (index - last_event_index) > self.config.reclaim_dedup_bars)
            ):
                candidate = _ReferenceCandidate(
                    reference_price=reference_price,
                    reference_timestamp=reference_timestamp,
                    start_index=index,
                    start_timestamp=bar.bar_timestamp,
                    sweep_low=bar.low_price,
                    reentry_index=index if bar.close_price > reference_price else None,
                )
                status = "CANDIDATE"

        if status == "NONE" and candidate is not None:
            status = "CANDIDATE"

        result = LifecyclePatternResult(
            status=status,
            reference_price=active_event.reference_price if active_event is not None else candidate.reference_price if candidate is not None else None,
            reference_timestamp=active_event.reference_timestamp if active_event is not None else candidate.reference_timestamp if candidate is not None else None,
            sweep_low=candidate.sweep_low if candidate is not None else None,
            candidate_start_timestamp=candidate.start_timestamp if candidate is not None else None,
            event_timestamp=active_event.event_timestamp if active_event is not None else None,
        )
        return result, candidate, active_event, emitted_event

    def _advance_fake_breakdown(
        self,
        bar: EngineBar,
        index: int,
        atr_value: Decimal,
        structure_result: StructureEngineResult,
        zone_result: ZoneEngineResult,
        candidate: _ReferenceCandidate | None,
        active_event: _ReferenceEvent | None,
        last_event_index_by_reference: dict[object, int],
    ) -> tuple[LifecyclePatternResult, _ReferenceCandidate | None, _ReferenceEvent | None, _ReferenceEvent | None]:
        emitted_event: _ReferenceEvent | None = None
        status = "NONE"
        reference_price, reference_timestamp = self._support_reference(structure_result, zone_result)

        if active_event is not None:
            if bar.close_price < active_event.reference_price:
                status = "INVALIDATED"
                active_event = None
            elif active_event.active_until is not None and index <= active_event.active_until:
                status = "ACTIVE"
            else:
                active_event = None

        if candidate is not None:
            candidate.sweep_low = min(candidate.sweep_low, bar.low_price)
            max_extension_price = candidate.reference_price - (self.config.fake_breakdown_max_extension_atr * atr_value)
            if candidate.sweep_low < max_extension_price:
                status = "INVALIDATED"
                candidate = None
            elif bar.close_price > candidate.reference_price and (index - candidate.start_index) <= self.config.fake_breakdown_reentry_window_bars:
                emitted_event = _ReferenceEvent(
                    reference_price=candidate.reference_price,
                    reference_timestamp=candidate.reference_timestamp,
                    event_index=index,
                    event_timestamp=bar.bar_timestamp,
                    active_until=index + self.config.fake_breakdown_active_bars,
                )
                active_event = emitted_event
                candidate = None
                status = "NEW_EVENT"
            elif (index - candidate.start_index) > self.config.fake_breakdown_reentry_window_bars:
                status = "INVALIDATED"
                candidate = None

        if active_event is None and candidate is None and reference_price is not None and reference_timestamp is not None:
            last_event_index = last_event_index_by_reference.get(reference_timestamp)
            if (
                bar.low_price < reference_price
                and (last_event_index is None or (index - last_event_index) > self.config.fake_breakdown_dedup_bars)
            ):
                candidate = _ReferenceCandidate(
                    reference_price=reference_price,
                    reference_timestamp=reference_timestamp,
                    start_index=index,
                    start_timestamp=bar.bar_timestamp,
                    sweep_low=bar.low_price,
                )
                status = "CANDIDATE"

        if status == "NONE" and candidate is not None:
            status = "CANDIDATE"

        result = LifecyclePatternResult(
            status=status,
            reference_price=active_event.reference_price if active_event is not None else candidate.reference_price if candidate is not None else None,
            reference_timestamp=active_event.reference_timestamp if active_event is not None else candidate.reference_timestamp if candidate is not None else None,
            sweep_low=candidate.sweep_low if candidate is not None else None,
            candidate_start_timestamp=candidate.start_timestamp if candidate is not None else None,
            event_timestamp=active_event.event_timestamp if active_event is not None else None,
        )
        return result, candidate, active_event, emitted_event

    def _advance_trap_reverse(
        self,
        bar: EngineBar,
        index: int,
        structure_history: Sequence[StructureEngineResult],
        zone_result: ZoneEngineResult,
        fake_history: Sequence[_ReferenceEvent],
        reclaim_history: Sequence[_ReferenceEvent],
        active_event: _ReferenceEvent | None,
        active_trigger: str | None,
        last_event_index_by_key: dict[tuple[object, str], int],
    ) -> tuple[TrapReverseResult, _ReferenceEvent | None, str | None, _ReferenceEvent | None]:
        emitted_event: _ReferenceEvent | None = None
        status = "NONE"

        if active_event is not None:
            if bar.close_price < active_event.reference_price:
                status = "INVALIDATED"
                active_event = None
                active_trigger = None
            elif active_event.active_until is not None and index <= active_event.active_until:
                status = "ACTIVE"
            else:
                active_event = None
                active_trigger = None

        recent_fake_events = [
            event
            for event in fake_history
            if (index - event.event_index) <= self.config.trap_reverse_lookback_bars
        ]

        if active_event is None:
            for fake_event in sorted(recent_fake_events, key=lambda event: event.event_index, reverse=True):
                matching_reclaim = next(
                    (
                        reclaim_event
                        for reclaim_event in reversed(reclaim_history)
                        if reclaim_event.reference_timestamp == fake_event.reference_timestamp
                        and reclaim_event.event_index >= fake_event.event_index
                    ),
                    None,
                )
                bullish_structure_events = [
                    event
                    for structure_result in structure_history[fake_event.event_index : index + 1]
                    for event in structure_result.events_on_bar
                    if event.event_type in {"BULLISH_CHOCH", "BULLISH_BOS"}
                ]
                if (
                    matching_reclaim is not None
                    and bullish_structure_events
                    and zone_result.zone_location in {"DISCOUNT", "EQUILIBRIUM"}
                ):
                    trigger_event = bullish_structure_events[-1].event_type
                    last_event_index = last_event_index_by_key.get((fake_event.reference_timestamp, trigger_event))
                    if last_event_index is not None and (index - last_event_index) <= self.config.trap_reverse_lookback_bars:
                        continue
                    emitted_event = _ReferenceEvent(
                        reference_price=fake_event.reference_price,
                        reference_timestamp=fake_event.reference_timestamp,
                        event_index=index,
                        event_timestamp=bar.bar_timestamp,
                        active_until=index + self.config.trap_reverse_active_bars,
                    )
                    active_event = emitted_event
                    active_trigger = trigger_event
                    status = "NEW_EVENT"
                    break
                if bar.close_price < fake_event.reference_price:
                    status = "INVALIDATED"
                    break

        result = TrapReverseResult(
            status=status,
            reference_price=active_event.reference_price if active_event is not None else None,
            reference_timestamp=active_event.reference_timestamp if active_event is not None else None,
            trigger_event=active_trigger,
            event_timestamp=active_event.event_timestamp if active_event is not None else None,
        )
        return result, active_event, active_trigger, emitted_event

    def _advance_recontainment(
        self,
        bars: Sequence[EngineBar],
        index: int,
        atr_value: Decimal | None,
        structure_history: Sequence[StructureEngineResult],
        zone_result: ZoneEngineResult,
        displacement_history: Sequence[_DisplacementRecord],
        current_state: _RecontainmentState,
    ) -> tuple[RecontainmentResult, _RecontainmentState, str | None]:
        if current_state.status == "INVALIDATED":
            current_state = _RecontainmentState()

        bar = bars[index]
        event_type: str | None = None
        previous_status = current_state.status
        recent_displacement = next(
            (
                record
                for record in reversed(displacement_history)
                if (index - record.bar_index) <= self.config.recontainment_lookback_bars
            ),
            None,
        )

        source_displacement = (
            current_state.source_displacement
            if previous_status in {"CANDIDATE", "ACTIVE"} and current_state.source_displacement is not None
            else recent_displacement
        )

        if atr_value is None or source_displacement is None or zone_result.range_status == "NO_VALID_RANGE":
            if previous_status in {"CANDIDATE", "ACTIVE"}:
                invalidated_state = _RecontainmentState(status="INVALIDATED")
                return self._build_recontainment_result(invalidated_state, zone_result), invalidated_state, "RECONTAINMENT_INVALIDATED"
            return self._build_recontainment_result(_RecontainmentState(), zone_result), _RecontainmentState(), None

        extension_limit = source_displacement.event_high + (self.config.recontainment_max_extension_atr * atr_value)
        highs_since_displacement = max(history_bar.high_price for history_bar in bars[source_displacement.bar_index : index + 1])
        inside_range = (
            zone_result.active_swing_low <= bar.low_price <= zone_result.active_swing_high
            or zone_result.active_swing_low <= bar.close_price <= zone_result.active_swing_high
        )

        candidate_start_index = current_state.candidate_start_index if current_state.candidate_start_index is not None else index
        bearish_bos_since_candidate = any(
            event.event_type == "BEARISH_BOS"
            for structure_result in structure_history[candidate_start_index : index + 1]
            for event in structure_result.events_on_bar
        )

        candidate_conditions = highs_since_displacement <= extension_limit and inside_range
        active_conditions = (
            candidate_conditions
            and zone_result.zone_location in {"DISCOUNT", "EQUILIBRIUM"}
            and bar.close_price >= zone_result.active_swing_low
            and not bearish_bos_since_candidate
            and zone_result.range_status == "RANGE_AVAILABLE"
        )

        if previous_status in {"CANDIDATE", "ACTIVE"} and (
            not candidate_conditions
            or bearish_bos_since_candidate
            or bar.close_price < zone_result.active_swing_low
        ):
            invalidated_state = _RecontainmentState(status="INVALIDATED")
            return self._build_recontainment_result(invalidated_state, zone_result), invalidated_state, "RECONTAINMENT_INVALIDATED"

        if candidate_conditions:
            if previous_status == "NONE":
                current_state = _RecontainmentState(
                    status="CANDIDATE",
                    source_displacement=source_displacement,
                    candidate_start_index=index,
                    candidate_start_timestamp=bar.bar_timestamp,
                )

            if active_conditions:
                event_type = "RECONTAINMENT_ENTERED" if previous_status != "ACTIVE" else None
                current_state = _RecontainmentState(
                    status="ACTIVE",
                    source_displacement=source_displacement,
                    candidate_start_index=current_state.candidate_start_index,
                    candidate_start_timestamp=current_state.candidate_start_timestamp,
                )
            else:
                current_state = _RecontainmentState(
                    status="CANDIDATE",
                    source_displacement=source_displacement,
                    candidate_start_index=current_state.candidate_start_index,
                    candidate_start_timestamp=current_state.candidate_start_timestamp,
                )
        else:
            current_state = _RecontainmentState()

        return self._build_recontainment_result(current_state, zone_result), current_state, event_type

    def _build_recontainment_result(
        self,
        state: _RecontainmentState,
        zone_result: ZoneEngineResult,
    ) -> RecontainmentResult:
        status = state.status if state.status in {"NONE", "CANDIDATE", "ACTIVE", "INVALIDATED"} else "NONE"
        return RecontainmentResult(
            status=status,
            source_displacement_timestamp=state.source_displacement.event_timestamp if state.source_displacement else None,
            source_displacement_reference_price=state.source_displacement.reference_price if state.source_displacement else None,
            candidate_start_timestamp=state.candidate_start_timestamp,
            active_range_low=zone_result.active_swing_low,
            active_range_high=zone_result.active_swing_high,
        )

    def _support_reference(
        self,
        structure_result: StructureEngineResult,
        zone_result: ZoneEngineResult,
    ) -> tuple[Decimal | None, object | None]:
        if zone_result.range_status == "RANGE_AVAILABLE":
            return zone_result.active_swing_low, zone_result.active_swing_low_timestamp

        for swing in reversed(structure_result.swing_points):
            if swing.kind == "LOW":
                return swing.price, swing.pivot_timestamp
        return None, None

    def _build_active_flags(
        self,
        compression: CompressionResult,
        displacement: DisplacementResult,
        reclaim: LifecyclePatternResult,
        fake_breakdown: LifecyclePatternResult,
        trap_reverse: TrapReverseResult,
        recontainment: RecontainmentResult,
    ) -> list[ActiveFlag]:
        active_flags: list[ActiveFlag] = []
        if compression.status == "COMPRESSED":
            active_flags.append("COMPRESSION")
        if displacement.status in {"NEW_EVENT", "ACTIVE"}:
            active_flags.append("BULLISH_DISPLACEMENT")
        if reclaim.status in {"NEW_EVENT", "ACTIVE"}:
            active_flags.append("BULLISH_RECLAIM")
        if fake_breakdown.status in {"NEW_EVENT", "ACTIVE"}:
            active_flags.append("BULLISH_FAKE_BREAKDOWN")
        if trap_reverse.status in {"NEW_EVENT", "ACTIVE"}:
            active_flags.append("BULLISH_TRAP_REVERSE")
        if recontainment.status == "CANDIDATE":
            active_flags.append("RECONTAINMENT_CANDIDATE")
        if recontainment.status == "ACTIVE":
            active_flags.append("RECONTAINMENT_ACTIVE")
        return active_flags
