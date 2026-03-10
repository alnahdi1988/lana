from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from doctrine_engine.engines.models import (
    EngineBar,
    StructureEngineResult,
    StructureEvent,
    StructureReferenceLevels,
    SwingPoint,
    TrendState,
)


@dataclass(frozen=True, slots=True)
class StructureEngineConfig:
    pivot_window: int = 2
    config_version: str = "v1"


@dataclass(frozen=True, slots=True)
class _PendingSwing:
    kind: str
    pivot_index: int
    confirm_index: int
    price: Decimal


@dataclass(frozen=True, slots=True)
class _ReferenceCandidate:
    reference_swing: SwingPoint
    protected_swing: SwingPoint


@dataclass(frozen=True, slots=True)
class _BosEventContext:
    event: StructureEvent
    reference_swing: SwingPoint
    protected_swing: SwingPoint


class StructureEngine:
    def __init__(self, config: StructureEngineConfig | None = None) -> None:
        self.config = config or StructureEngineConfig()

    def evaluate(self, bars: Sequence[EngineBar]) -> StructureEngineResult:
        return self.evaluate_history(bars)[-1]

    def evaluate_history(self, bars: Sequence[EngineBar]) -> list[StructureEngineResult]:
        ordered_bars = self._validate_bars(bars)
        pending_by_confirm_index = self._build_pending_swings(ordered_bars)
        normalized_swings: list[SwingPoint] = []
        bullish_bos_history: list[_BosEventContext] = []
        bearish_bos_history: list[_BosEventContext] = []
        results: list[StructureEngineResult] = []

        for current_index, current_bar in enumerate(ordered_bars):
            for pending in pending_by_confirm_index.get(current_index, []):
                confirmed_swing = SwingPoint(
                    kind="HIGH" if pending.kind == "HIGH" else "LOW",
                    pivot_timestamp=ordered_bars[pending.pivot_index].bar_timestamp,
                    confirmed_at=ordered_bars[pending.confirm_index].bar_timestamp,
                    price=pending.price,
                    sequence_index=-1,
                )
                self._add_normalized_swing(normalized_swings, confirmed_swing)

            swings_for_bar = self._reindex_swings(normalized_swings)
            prior_bars = ordered_bars[:current_index]
            bullish_bos_candidate = self._select_bullish_bos_reference(
                swings_for_bar,
                prior_bars,
                current_bar.bar_timestamp,
            )
            bearish_bos_candidate = self._select_bearish_bos_reference(
                swings_for_bar,
                prior_bars,
                current_bar.bar_timestamp,
            )
            bullish_choch_reference = self._select_bullish_choch_reference(swings_for_bar, prior_bars)
            bearish_choch_reference = self._select_bearish_choch_reference(swings_for_bar, prior_bars)

            events_on_bar: list[StructureEvent] = []

            if bullish_bos_candidate and current_bar.close_price > bullish_bos_candidate.reference_swing.price:
                bullish_event = StructureEvent(
                    event_type="BULLISH_BOS",
                    event_timestamp=current_bar.bar_timestamp,
                    reference_timestamp=bullish_bos_candidate.reference_swing.pivot_timestamp,
                    reference_price=bullish_bos_candidate.reference_swing.price,
                    close_price=current_bar.close_price,
                )
                bullish_bos_history.append(
                    _BosEventContext(
                        event=bullish_event,
                        reference_swing=bullish_bos_candidate.reference_swing,
                        protected_swing=bullish_bos_candidate.protected_swing,
                    )
                )
                events_on_bar.append(bullish_event)

            if bearish_bos_candidate and current_bar.close_price < bearish_bos_candidate.reference_swing.price:
                bearish_event = StructureEvent(
                    event_type="BEARISH_BOS",
                    event_timestamp=current_bar.bar_timestamp,
                    reference_timestamp=bearish_bos_candidate.reference_swing.pivot_timestamp,
                    reference_price=bearish_bos_candidate.reference_swing.price,
                    close_price=current_bar.close_price,
                )
                bearish_bos_history.append(
                    _BosEventContext(
                        event=bearish_event,
                        reference_swing=bearish_bos_candidate.reference_swing,
                        protected_swing=bearish_bos_candidate.protected_swing,
                    )
                )
                events_on_bar.append(bearish_event)

            if bullish_choch_reference and current_bar.close_price > bullish_choch_reference.price:
                events_on_bar.append(
                    StructureEvent(
                        event_type="BULLISH_CHOCH",
                        event_timestamp=current_bar.bar_timestamp,
                        reference_timestamp=bullish_choch_reference.pivot_timestamp,
                        reference_price=bullish_choch_reference.price,
                        close_price=current_bar.close_price,
                    )
                )

            if bearish_choch_reference and current_bar.close_price < bearish_choch_reference.price:
                events_on_bar.append(
                    StructureEvent(
                        event_type="BEARISH_CHOCH",
                        event_timestamp=current_bar.bar_timestamp,
                        reference_timestamp=bearish_choch_reference.pivot_timestamp,
                        reference_price=bearish_choch_reference.price,
                        close_price=current_bar.close_price,
                    )
                )

            events_on_bar.sort(
                key=lambda event: {
                    "BULLISH_BOS": 0,
                    "BEARISH_BOS": 1,
                    "BULLISH_CHOCH": 2,
                    "BEARISH_CHOCH": 3,
                }[event.event_type]
            )

            (
                active_range_selection,
                active_range_low,
                active_range_low_timestamp,
                active_range_high,
                active_range_high_timestamp,
            ) = self._select_active_range(
                current_close=current_bar.close_price,
                swings=swings_for_bar,
                bullish_bos_history=bullish_bos_history,
                bearish_bos_history=bearish_bos_history,
            )

            results.append(
                StructureEngineResult(
                    symbol_id=current_bar.symbol_id,
                    timeframe=current_bar.timeframe,
                    bar_timestamp=current_bar.bar_timestamp,
                    known_at=current_bar.known_at,
                    config_version=self.config.config_version,
                    pivot_window=self.config.pivot_window,
                    swing_points=swings_for_bar,
                    reference_levels=StructureReferenceLevels(
                        bullish_bos_reference_price=(
                            bullish_bos_candidate.reference_swing.price if bullish_bos_candidate else None
                        ),
                        bullish_bos_reference_timestamp=(
                            bullish_bos_candidate.reference_swing.pivot_timestamp if bullish_bos_candidate else None
                        ),
                        bullish_bos_protected_low_price=(
                            bullish_bos_candidate.protected_swing.price if bullish_bos_candidate else None
                        ),
                        bullish_bos_protected_low_timestamp=(
                            bullish_bos_candidate.protected_swing.pivot_timestamp if bullish_bos_candidate else None
                        ),
                        bearish_bos_reference_price=(
                            bearish_bos_candidate.reference_swing.price if bearish_bos_candidate else None
                        ),
                        bearish_bos_reference_timestamp=(
                            bearish_bos_candidate.reference_swing.pivot_timestamp if bearish_bos_candidate else None
                        ),
                        bearish_bos_protected_high_price=(
                            bearish_bos_candidate.protected_swing.price if bearish_bos_candidate else None
                        ),
                        bearish_bos_protected_high_timestamp=(
                            bearish_bos_candidate.protected_swing.pivot_timestamp if bearish_bos_candidate else None
                        ),
                        bullish_choch_reference_price=(
                            bullish_choch_reference.price if bullish_choch_reference else None
                        ),
                        bullish_choch_reference_timestamp=(
                            bullish_choch_reference.pivot_timestamp if bullish_choch_reference else None
                        ),
                        bearish_choch_reference_price=(
                            bearish_choch_reference.price if bearish_choch_reference else None
                        ),
                        bearish_choch_reference_timestamp=(
                            bearish_choch_reference.pivot_timestamp if bearish_choch_reference else None
                        ),
                    ),
                    active_range_selection=active_range_selection,
                    active_range_low=active_range_low,
                    active_range_low_timestamp=active_range_low_timestamp,
                    active_range_high=active_range_high,
                    active_range_high_timestamp=active_range_high_timestamp,
                    trend_state=self._determine_trend_state(swings_for_bar),
                    events_on_bar=events_on_bar,
                )
            )

        return results

    def _validate_bars(self, bars: Sequence[EngineBar]) -> list[EngineBar]:
        if not bars:
            raise ValueError("StructureEngine requires at least one bar.")

        ordered = sorted(bars, key=lambda bar: bar.bar_timestamp)
        first = ordered[0]
        for bar in ordered[1:]:
            if bar.symbol_id != first.symbol_id:
                raise ValueError("All bars must share the same symbol_id.")
            if bar.timeframe != first.timeframe:
                raise ValueError("All bars must share the same timeframe.")
        return ordered

    def _build_pending_swings(self, bars: Sequence[EngineBar]) -> dict[int, list[_PendingSwing]]:
        pending_by_confirm_index: dict[int, list[_PendingSwing]] = {}
        window = self.config.pivot_window
        if len(bars) < (window * 2) + 1:
            return pending_by_confirm_index

        for pivot_index in range(window, len(bars) - window):
            left = bars[pivot_index - window : pivot_index]
            right = bars[pivot_index + 1 : pivot_index + window + 1]
            current = bars[pivot_index]

            is_swing_high = all(current.high_price > bar.high_price for bar in left) and all(
                current.high_price > bar.high_price for bar in right
            )
            is_swing_low = all(current.low_price < bar.low_price for bar in left) and all(
                current.low_price < bar.low_price for bar in right
            )

            if is_swing_high:
                pending_by_confirm_index.setdefault(pivot_index + window, []).append(
                    _PendingSwing(
                        kind="HIGH",
                        pivot_index=pivot_index,
                        confirm_index=pivot_index + window,
                        price=current.high_price,
                    )
                )

            if is_swing_low:
                pending_by_confirm_index.setdefault(pivot_index + window, []).append(
                    _PendingSwing(
                        kind="LOW",
                        pivot_index=pivot_index,
                        confirm_index=pivot_index + window,
                        price=current.low_price,
                    )
                )

        return pending_by_confirm_index

    def _add_normalized_swing(self, normalized_swings: list[SwingPoint], swing: SwingPoint) -> None:
        if not normalized_swings:
            normalized_swings.append(swing)
            return

        last = normalized_swings[-1]
        if last.kind != swing.kind:
            normalized_swings.append(swing)
            return

        should_replace = False
        if swing.kind == "HIGH" and swing.price > last.price:
            should_replace = True
        elif swing.kind == "LOW" and swing.price < last.price:
            should_replace = True
        elif swing.price == last.price and swing.pivot_timestamp < last.pivot_timestamp:
            should_replace = True

        if should_replace:
            normalized_swings[-1] = swing

    def _reindex_swings(self, swings: Sequence[SwingPoint]) -> list[SwingPoint]:
        return [
            SwingPoint(
                kind=swing.kind,
                pivot_timestamp=swing.pivot_timestamp,
                confirmed_at=swing.confirmed_at,
                price=swing.price,
                sequence_index=index,
            )
            for index, swing in enumerate(swings)
        ]

    def _select_bullish_bos_reference(
        self,
        swings: Sequence[SwingPoint],
        prior_bars: Sequence[EngineBar],
        current_bar_timestamp: datetime,
    ) -> _ReferenceCandidate | None:
        highs = [swing for swing in swings if swing.kind == "HIGH"]
        lows = [swing for swing in swings if swing.kind == "LOW"]

        for high in sorted(highs, key=lambda swing: swing.pivot_timestamp, reverse=True):
            if self._has_close_above_reference(prior_bars, high):
                continue
            protected_lows = [
                low
                for low in lows
                if low.pivot_timestamp > high.pivot_timestamp and low.confirmed_at <= current_bar_timestamp
            ]
            if protected_lows:
                return _ReferenceCandidate(
                    reference_swing=high,
                    protected_swing=max(protected_lows, key=lambda swing: swing.pivot_timestamp),
                )
        return None

    def _select_bearish_bos_reference(
        self,
        swings: Sequence[SwingPoint],
        prior_bars: Sequence[EngineBar],
        current_bar_timestamp: datetime,
    ) -> _ReferenceCandidate | None:
        highs = [swing for swing in swings if swing.kind == "HIGH"]
        lows = [swing for swing in swings if swing.kind == "LOW"]

        for low in sorted(lows, key=lambda swing: swing.pivot_timestamp, reverse=True):
            if self._has_close_below_reference(prior_bars, low):
                continue
            protected_highs = [
                high
                for high in highs
                if high.pivot_timestamp > low.pivot_timestamp and high.confirmed_at <= current_bar_timestamp
            ]
            if protected_highs:
                return _ReferenceCandidate(
                    reference_swing=low,
                    protected_swing=max(protected_highs, key=lambda swing: swing.pivot_timestamp),
                )
        return None

    def _select_bullish_choch_reference(
        self,
        swings: Sequence[SwingPoint],
        prior_bars: Sequence[EngineBar],
    ) -> SwingPoint | None:
        if len(swings) < 4:
            return None

        for start_index in range(len(swings) - 4, -1, -1):
            window = swings[start_index : start_index + 4]
            if [swing.kind for swing in window] != ["HIGH", "LOW", "HIGH", "LOW"]:
                continue
            first_high, first_low, lower_high, lower_low = window
            if lower_high.price < first_high.price and lower_low.price < first_low.price:
                if not self._has_close_above_reference(prior_bars, lower_high):
                    return lower_high
        return None

    def _select_bearish_choch_reference(
        self,
        swings: Sequence[SwingPoint],
        prior_bars: Sequence[EngineBar],
    ) -> SwingPoint | None:
        if len(swings) < 4:
            return None

        for start_index in range(len(swings) - 4, -1, -1):
            window = swings[start_index : start_index + 4]
            if [swing.kind for swing in window] != ["LOW", "HIGH", "LOW", "HIGH"]:
                continue
            first_low, first_high, higher_low, higher_high = window
            if higher_low.price > first_low.price and higher_high.price > first_high.price:
                if not self._has_close_below_reference(prior_bars, higher_low):
                    return higher_low
        return None

    def _has_close_above_reference(self, bars: Sequence[EngineBar], reference: SwingPoint) -> bool:
        return any(
            bar.bar_timestamp >= reference.confirmed_at and bar.close_price > reference.price
            for bar in bars
        )

    def _has_close_below_reference(self, bars: Sequence[EngineBar], reference: SwingPoint) -> bool:
        return any(
            bar.bar_timestamp >= reference.confirmed_at and bar.close_price < reference.price
            for bar in bars
        )

    def _determine_trend_state(self, swings: Sequence[SwingPoint]) -> TrendState:
        if len(swings) < 4:
            return "UNDEFINED"

        window = swings[-4:]
        kinds = [swing.kind for swing in window]
        if kinds == ["HIGH", "LOW", "HIGH", "LOW"]:
            if window[2].price > window[0].price and window[3].price > window[1].price:
                return "BULLISH_SEQUENCE"
            if window[2].price < window[0].price and window[3].price < window[1].price:
                return "BEARISH_SEQUENCE"
            return "MIXED"

        if kinds == ["LOW", "HIGH", "LOW", "HIGH"]:
            if window[2].price > window[0].price and window[3].price > window[1].price:
                return "BULLISH_SEQUENCE"
            if window[2].price < window[0].price and window[3].price < window[1].price:
                return "BEARISH_SEQUENCE"
            return "MIXED"

        return "MIXED"

    def _select_active_range(
        self,
        current_close: Decimal,
        swings: Sequence[SwingPoint],
        bullish_bos_history: Sequence[_BosEventContext],
        bearish_bos_history: Sequence[_BosEventContext],
    ) -> tuple[str, Decimal | None, object | None, Decimal | None, object | None]:
        bos_candidates: list[tuple[StructureEvent, SwingPoint, SwingPoint]] = []
        bos_candidates.extend(
            (context.event, context.protected_swing, context.reference_swing)
            for context in bullish_bos_history
        )
        bos_candidates.extend(
            (context.event, context.reference_swing, context.protected_swing)
            for context in bearish_bos_history
        )

        valid_bos_candidates = [
            candidate
            for candidate in bos_candidates
            if candidate[1] is not None and candidate[2] is not None
        ]
        if valid_bos_candidates:
            latest_event, low_swing, high_swing = max(
                valid_bos_candidates,
                key=lambda item: (
                    item[0].event_timestamp,
                    item[0].reference_timestamp,
                    abs(item[0].close_price - item[0].reference_price),
                ),
            )
            if latest_event.event_type == "BULLISH_BOS":
                low_swing = low_swing
                high_swing = high_swing
            else:
                low_swing = low_swing
                high_swing = high_swing
            return (
                "BOS_ANCHORED",
                low_swing.price,
                low_swing.pivot_timestamp,
                high_swing.price,
                high_swing.pivot_timestamp,
            )

        adjacent_pairs = self._adjacent_opposite_kind_pairs(swings)
        bracketing_pairs = []
        for left, right in adjacent_pairs:
            low_swing = left if left.kind == "LOW" else right
            high_swing = left if left.kind == "HIGH" else right
            if low_swing.price <= current_close <= high_swing.price:
                bracketing_pairs.append((left, right, low_swing, high_swing))

        if bracketing_pairs:
            _, _, low_swing, high_swing = max(
                bracketing_pairs,
                key=lambda item: (
                    max(item[0].pivot_timestamp, item[1].pivot_timestamp),
                    item[3].price - item[2].price,
                ),
            )
            return (
                "BRACKETING_PAIR",
                low_swing.price,
                low_swing.pivot_timestamp,
                high_swing.price,
                high_swing.pivot_timestamp,
            )

        if adjacent_pairs:
            left, right = max(
                adjacent_pairs,
                key=lambda pair: (
                    max(pair[0].pivot_timestamp, pair[1].pivot_timestamp),
                    abs(pair[0].price - pair[1].price),
                ),
            )
            low_swing = left if left.kind == "LOW" else right
            high_swing = left if left.kind == "HIGH" else right
            return (
                "LATEST_PAIR_FALLBACK",
                low_swing.price,
                low_swing.pivot_timestamp,
                high_swing.price,
                high_swing.pivot_timestamp,
            )

        return ("NO_VALID_RANGE", None, None, None, None)

    def _adjacent_opposite_kind_pairs(self, swings: Sequence[SwingPoint]) -> list[tuple[SwingPoint, SwingPoint]]:
        pairs: list[tuple[SwingPoint, SwingPoint]] = []
        for left, right in zip(swings[:-1], swings[1:]):
            if left.kind != right.kind:
                pairs.append((left, right))
        return pairs
