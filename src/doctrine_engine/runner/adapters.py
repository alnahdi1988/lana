from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from doctrine_engine.alerts.models import PriorAlertState
from doctrine_engine.event_risk.models import EventRiskEngineInput
from doctrine_engine.regime.models import RegimeEngineInput
from doctrine_engine.runner.models import (
    BenchmarkPhaseContext,
    PersistedPhase2Context,
    RunnerInput,
    SymbolMarketContext,
    UniverseSymbolContext,
)


class UniverseContextLoader(Protocol):
    def load(self, runner_input: RunnerInput) -> list[UniverseSymbolContext]: ...


class MarketDataLoader(Protocol):
    def load_symbol_context(self, symbol: UniverseSymbolContext, runner_input: RunnerInput) -> SymbolMarketContext: ...

    def load_benchmark_context(self, runner_input: RunnerInput) -> BenchmarkPhaseContext: ...


class Phase2FeatureLoader(Protocol):
    def load(self, symbol: UniverseSymbolContext, runner_input: RunnerInput) -> PersistedPhase2Context | None: ...


class RegimeExternalInputLoader(Protocol):
    def load(
        self,
        symbol: UniverseSymbolContext,
        benchmark_context: BenchmarkPhaseContext,
        runner_input: RunnerInput,
    ) -> RegimeEngineInput: ...


class EventRiskExternalInputLoader(Protocol):
    def load(
        self,
        symbol: UniverseSymbolContext,
        signal_time_baseline: datetime,
        known_at_baseline: datetime,
        runner_input: RunnerInput,
    ) -> EventRiskEngineInput: ...


class PriorAlertStateLoader(Protocol):
    def load(self, symbol_id: uuid.UUID, setup_state: str, entry_type: str) -> PriorAlertState | None: ...


__all__ = [
    "EventRiskExternalInputLoader",
    "MarketDataLoader",
    "Phase2FeatureLoader",
    "PriorAlertStateLoader",
    "RegimeExternalInputLoader",
    "UniverseContextLoader",
]
