from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from doctrine_engine.engines.models import EngineBar, StructureEngineResult, ZoneEngineResult


@dataclass(frozen=True, slots=True)
class ZoneEngineConfig:
    equilibrium_band_ratio: Decimal = Decimal("0.05")
    config_version: str = "v1"


class ZoneEngine:
    def __init__(self, config: ZoneEngineConfig | None = None) -> None:
        self.config = config or ZoneEngineConfig()

    def evaluate(self, bars: Sequence[EngineBar], structure_result: StructureEngineResult) -> ZoneEngineResult:
        if not bars:
            raise ValueError("ZoneEngine requires at least one bar.")
        return self.evaluate_history([bars[-1]], [structure_result])[-1]

    def evaluate_history(
        self,
        bars: Sequence[EngineBar],
        structure_history: Sequence[StructureEngineResult],
    ) -> list[ZoneEngineResult]:
        if len(bars) != len(structure_history):
            raise ValueError("ZoneEngine requires one structure result per bar.")

        results: list[ZoneEngineResult] = []
        for bar, structure_result in zip(bars, structure_history):
            if structure_result.active_range_selection == "NO_VALID_RANGE":
                results.append(
                    ZoneEngineResult(
                        symbol_id=bar.symbol_id,
                        timeframe=bar.timeframe,
                        bar_timestamp=bar.bar_timestamp,
                        known_at=bar.known_at,
                        config_version=self.config.config_version,
                        range_status="NO_VALID_RANGE",
                        selection_reason="NO_VALID_RANGE",
                        active_swing_low=None,
                        active_swing_low_timestamp=None,
                        active_swing_high=None,
                        active_swing_high_timestamp=None,
                        range_width=None,
                        equilibrium=None,
                        equilibrium_band_low=None,
                        equilibrium_band_high=None,
                        zone_location="NO_VALID_RANGE",
                        distance_from_equilibrium=None,
                        distance_from_equilibrium_pct_of_range=None,
                    )
                )
                continue

            range_width = structure_result.active_range_high - structure_result.active_range_low
            equilibrium = (structure_result.active_range_high + structure_result.active_range_low) / Decimal("2")
            equilibrium_band_half_width = range_width * self.config.equilibrium_band_ratio
            equilibrium_band_low = equilibrium - equilibrium_band_half_width
            equilibrium_band_high = equilibrium + equilibrium_band_half_width
            distance_from_equilibrium = bar.close_price - equilibrium
            distance_from_equilibrium_pct_of_range = (
                distance_from_equilibrium / range_width if range_width != 0 else Decimal("0")
            )

            if bar.close_price < equilibrium_band_low:
                zone_location = "DISCOUNT"
            elif bar.close_price > equilibrium_band_high:
                zone_location = "PREMIUM"
            else:
                zone_location = "EQUILIBRIUM"

            results.append(
                ZoneEngineResult(
                    symbol_id=bar.symbol_id,
                    timeframe=bar.timeframe,
                    bar_timestamp=bar.bar_timestamp,
                    known_at=bar.known_at,
                    config_version=self.config.config_version,
                    range_status="RANGE_AVAILABLE",
                    selection_reason=structure_result.active_range_selection,
                    active_swing_low=structure_result.active_range_low,
                    active_swing_low_timestamp=structure_result.active_range_low_timestamp,
                    active_swing_high=structure_result.active_range_high,
                    active_swing_high_timestamp=structure_result.active_range_high_timestamp,
                    range_width=range_width,
                    equilibrium=equilibrium,
                    equilibrium_band_low=equilibrium_band_low,
                    equilibrium_band_high=equilibrium_band_high,
                    zone_location=zone_location,
                    distance_from_equilibrium=distance_from_equilibrium,
                    distance_from_equilibrium_pct_of_range=distance_from_equilibrium_pct_of_range,
                )
            )

        return results
