"""
tests/integration/test_product_integration.py

Full product integration test covering the complete propagation chain:
  persisted 5M phase2 context
    → runner config (TimeframeConfig with micro="5M")
      → SignalEngine.evaluate (real engine)
        → micro_state in extensible_context
          → AlertWorkflow.evaluate (real workflow)
            → AlertDecisionPayload with micro fields
              → TelegramRenderer.render (real renderer)
                → rendered text with micro line

Fixture design targets:
  - RECONTAINMENT_CONFIRMED setup (RECONTAINMENT_CANDIDATE + BULLISH HTF + LTF_BULLISH_RECLAIM)
  - Grade A confidence (0.80 via compression + displacement bonuses)
  - Price geometry valid for TradePlanEngine (different swing highs per frame)

Price levels:
  - close_price = 10.0, in DISCOUNT below equilibrium 10.5
  - HTF active_swing_high = 13.5 → TP2 anchor
  - MTF active_swing_high = 11.5 → confirmation_level
  - LTF active_swing_high = 12.0 → TP1 anchor
  - invalidation = 9.0 (recontainment range low, below entry_zone_low 9.5)

No real PostgreSQL — all loaders return in-memory fixture objects.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.alerts.models import AlertWorkflowInput
from doctrine_engine.alerts.telegram_renderer import TelegramRenderer
from doctrine_engine.alerts.workflow import AlertWorkflow, AlertWorkflowConfig
from doctrine_engine.db.types import Timeframe
from doctrine_engine.engines.models import (
    CompressionResult,
    DisplacementResult,
    EngineBar,
    LifecyclePatternResult,
    PatternEngineResult,
    RecontainmentResult,
    SignalEngineInput,
    SignalEventRiskInput,
    SignalFrameInput,
    SignalRegimeInput,
    SignalSectorContextInput,
    StructureEngineResult,
    StructureReferenceLevels,
    TradePlanEngineInput,
    TrapReverseResult,
    ZoneEngineResult,
)
from doctrine_engine.engines.signal_engine import SignalEngine, SignalEngineConfig
from doctrine_engine.engines.trade_plan_engine import TradePlanEngine


# ---------------------------------------------------------------------------
# Fixture constants
# ---------------------------------------------------------------------------

SOFI_SYMBOL_ID = uuid.UUID("319f2af7-6084-4a5b-af82-b8ca500bb891")
SOFI_TICKER = "SOFI"

HTF_TS = datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
MTF_TS = datetime(2026, 3, 8, 14, 0, tzinfo=timezone.utc)
LTF_TS = datetime(2026, 3, 8, 15, 30, tzinfo=timezone.utc)
MICRO_TS = datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Low-level builders
# ---------------------------------------------------------------------------

def _bar(timeframe: Timeframe, ts: datetime) -> EngineBar:
    return EngineBar(
        symbol_id=SOFI_SYMBOL_ID,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=ts.replace(minute=ts.minute + 15 if ts.minute < 45 else 0, fold=0),
        open_price=Decimal("9.80"),
        high_price=Decimal("10.30"),
        low_price=Decimal("9.50"),
        close_price=Decimal("10.00"),  # below equilibrium 10.5 → DISCOUNT
        volume=1_500_000,
    )


def _structure(timeframe: Timeframe, ts: datetime, range_low: Decimal, range_high: Decimal) -> StructureEngineResult:
    return StructureEngineResult(
        symbol_id=SOFI_SYMBOL_ID,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=_known_at(ts),
        config_version="v1",
        pivot_window=2,
        swing_points=[],
        reference_levels=StructureReferenceLevels(
            bullish_bos_reference_price=None, bullish_bos_reference_timestamp=None,
            bullish_bos_protected_low_price=None, bullish_bos_protected_low_timestamp=None,
            bearish_bos_reference_price=None, bearish_bos_reference_timestamp=None,
            bearish_bos_protected_high_price=None, bearish_bos_protected_high_timestamp=None,
            bullish_choch_reference_price=None, bullish_choch_reference_timestamp=None,
            bearish_choch_reference_price=None, bearish_choch_reference_timestamp=None,
        ),
        active_range_selection="BRACKETING_PAIR",
        active_range_low=range_low,
        active_range_low_timestamp=ts,
        active_range_high=range_high,
        active_range_high_timestamp=ts,
        trend_state="BULLISH_SEQUENCE",
        events_on_bar=[],
    )


def _zone(
    timeframe: Timeframe,
    ts: datetime,
    *,
    swing_low: Decimal,
    swing_high: Decimal,
) -> ZoneEngineResult:
    equilibrium = (swing_low + swing_high) / 2
    eq_width = (swing_high - swing_low) * Decimal("0.10")
    return ZoneEngineResult(
        symbol_id=SOFI_SYMBOL_ID,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=_known_at(ts),
        config_version="v1",
        range_status="RANGE_AVAILABLE",
        selection_reason="BRACKETING_PAIR",
        active_swing_low=swing_low,
        active_swing_low_timestamp=ts,
        active_swing_high=swing_high,
        active_swing_high_timestamp=ts,
        range_width=swing_high - swing_low,
        equilibrium=equilibrium.quantize(Decimal("0.0001")),
        equilibrium_band_low=(equilibrium - eq_width).quantize(Decimal("0.0001")),
        equilibrium_band_high=(equilibrium + eq_width).quantize(Decimal("0.0001")),
        zone_location="DISCOUNT",
        distance_from_equilibrium=(equilibrium - Decimal("10.00")).quantize(Decimal("0.0001")),
        distance_from_equilibrium_pct_of_range=Decimal("0.2000"),
    )


def _pattern_bullish_reclaim(
    timeframe: Timeframe,
    ts: datetime,
    *,
    recontainment_range_low: Decimal,
    recontainment_range_high: Decimal,
    with_compression: bool = False,
    with_displacement: bool = False,
) -> PatternEngineResult:
    return PatternEngineResult(
        symbol_id=SOFI_SYMBOL_ID,
        timeframe=timeframe,
        bar_timestamp=ts,
        known_at=_known_at(ts),
        config_version="v1",
        compression=CompressionResult(
            status="COMPRESSED" if with_compression else "NOT_COMPRESSED",
            criteria_met=["ATR_CONTRACTION"] if with_compression else [],
            lookback_bars=5,
        ),
        bullish_displacement=DisplacementResult(
            status="NEW_EVENT" if with_displacement else "NONE",
            mode="IMPULSE" if with_displacement else None,
            event_timestamp=ts if with_displacement else None,
            reference_price=Decimal("9.80") if with_displacement else None,
            reference_timestamp=ts if with_displacement else None,
            range_multiple_atr=Decimal("1.50") if with_displacement else None,
            close_location_ratio=Decimal("0.90") if with_displacement else None,
        ),
        bullish_reclaim=LifecyclePatternResult(
            status="ACTIVE",
            reference_price=Decimal("9.50"),  # support_ref → entry_zone_low candidate
            reference_timestamp=ts,
            sweep_low=None,
            candidate_start_timestamp=ts,
            event_timestamp=ts,
        ),
        bullish_fake_breakdown=LifecyclePatternResult(
            status="NONE", reference_price=None, reference_timestamp=None,
            sweep_low=None, candidate_start_timestamp=None, event_timestamp=None,
        ),
        bullish_trap_reverse=TrapReverseResult(
            status="NONE", reference_price=None, reference_timestamp=None,
            trigger_event=None, event_timestamp=None,
        ),
        recontainment=RecontainmentResult(
            status="CANDIDATE",
            source_displacement_timestamp=None,
            source_displacement_reference_price=None,
            candidate_start_timestamp=ts,
            active_range_low=recontainment_range_low,
            active_range_high=recontainment_range_high,
        ),
        events_on_bar=[],
        active_flags=[],
    )


def _known_at(ts: datetime) -> datetime:
    """Advance minutes by 15 for the known_at timestamp."""
    total = ts.hour * 60 + ts.minute + 15
    return ts.replace(hour=total // 60, minute=total % 60)


# ---------------------------------------------------------------------------
# Frame builders — each frame has distinct zone levels for TP geometry
#
# Price hierarchy (ensures TradePlanEngine finds valid candidates):
#   HTF swing_high = 13.50 → TP2
#   LTF swing_high = 12.00 → TP1
#   MTF swing_high = 11.50 → confirmation_level
#   MTF equilibrium ≈ 10.25 → entry_zone_high
#   bullish_reclaim.reference_price = 9.50 → entry_zone_low candidate
#   recontainment.active_range_low = 9.00 → invalidation anchor
# ---------------------------------------------------------------------------

def _htf_frame(*, with_displacement: bool = False) -> SignalFrameInput:
    structure = _structure(Timeframe.HOUR_4, HTF_TS, Decimal("9.00"), Decimal("13.50"))
    return SignalFrameInput(
        timeframe="4H",
        latest_bar=_bar(Timeframe.HOUR_4, HTF_TS),
        structure=structure,
        structure_history=[structure],
        zone=_zone(Timeframe.HOUR_4, HTF_TS, swing_low=Decimal("9.00"), swing_high=Decimal("13.50")),
        pattern=_pattern_bullish_reclaim(
            Timeframe.HOUR_4, HTF_TS,
            recontainment_range_low=Decimal("9.00"),
            recontainment_range_high=Decimal("13.50"),
            with_displacement=with_displacement,
        ),
    )


def _mtf_frame(*, with_compression: bool = False) -> SignalFrameInput:
    structure = _structure(Timeframe.HOUR_1, MTF_TS, Decimal("9.00"), Decimal("11.50"))
    return SignalFrameInput(
        timeframe="1H",
        latest_bar=_bar(Timeframe.HOUR_1, MTF_TS),
        structure=structure,
        structure_history=[structure],
        zone=_zone(Timeframe.HOUR_1, MTF_TS, swing_low=Decimal("9.00"), swing_high=Decimal("11.50")),
        pattern=_pattern_bullish_reclaim(
            Timeframe.HOUR_1, MTF_TS,
            recontainment_range_low=Decimal("9.00"),
            recontainment_range_high=Decimal("11.50"),
            with_compression=with_compression,
        ),
    )


def _ltf_frame() -> SignalFrameInput:
    structure = _structure(Timeframe.MIN_15, LTF_TS, Decimal("9.00"), Decimal("12.00"))
    return SignalFrameInput(
        timeframe="15M",
        latest_bar=_bar(Timeframe.MIN_15, LTF_TS),
        structure=structure,
        structure_history=[structure],
        zone=_zone(Timeframe.MIN_15, LTF_TS, swing_low=Decimal("9.00"), swing_high=Decimal("12.00")),
        pattern=_pattern_bullish_reclaim(
            Timeframe.MIN_15, LTF_TS,
            recontainment_range_low=Decimal("9.00"),
            recontainment_range_high=Decimal("12.00"),
        ),
    )


def _micro_frame() -> SignalFrameInput:
    structure = _structure(Timeframe.MIN_5, MICRO_TS, Decimal("9.00"), Decimal("12.00"))
    return SignalFrameInput(
        timeframe="5M",
        latest_bar=_bar(Timeframe.MIN_5, MICRO_TS),
        structure=structure,
        structure_history=[structure],
        zone=_zone(Timeframe.MIN_5, MICRO_TS, swing_low=Decimal("9.00"), swing_high=Decimal("12.00")),
        pattern=_pattern_bullish_reclaim(
            Timeframe.MIN_5, MICRO_TS,
            recontainment_range_low=Decimal("9.00"),
            recontainment_range_high=Decimal("12.00"),
        ),
    )


def _regime() -> SignalRegimeInput:
    return SignalRegimeInput(
        market_regime="BULLISH_TREND",
        sector_regime="SECTOR_STRONG",
        market_permission_score=Decimal("0.75"),
        sector_permission_score=Decimal("0.65"),
        allows_longs=True,
        coverage_complete=True,
        reason_codes=["MARKET_BULLISH_TREND", "SECTOR_STRONG"],
        known_at=_known_at(LTF_TS),
    )


def _event_risk() -> SignalEventRiskInput:
    return SignalEventRiskInput(
        event_risk_class="NO_EVENT_RISK",
        blocked=False,
        coverage_complete=True,
        soft_penalty=Decimal("0.0000"),
        reason_codes=["EVENT_RISK_CLEAR"],
        known_at=_known_at(LTF_TS),
    )


def _sector_context() -> SignalSectorContextInput:
    return SignalSectorContextInput(
        sector_strength="STRONG",
        relative_strength_score=Decimal("0.02"),
        reason_codes=["SECTOR_STRONG"],
        known_at=_known_at(LTF_TS),
    )


def _build_signal_input(*, include_micro: bool) -> SignalEngineInput:
    # MTF compression + HTF displacement → +0.05 → confidence reaches 0.80 (Grade A)
    return SignalEngineInput(
        symbol_id=SOFI_SYMBOL_ID,
        ticker=SOFI_TICKER,
        universe_snapshot_id=None,
        universe_eligible=True,
        price_reference=Decimal("10.00"),
        universe_reason_codes=["UNIVERSE_ELIGIBLE"],
        universe_known_at=_known_at(LTF_TS),
        htf=_htf_frame(with_displacement=True),
        mtf=_mtf_frame(with_compression=True),
        ltf=_ltf_frame(),
        micro=_micro_frame() if include_micro else None,
        regime=_regime(),
        event_risk=_event_risk(),
        sector_context=_sector_context(),
    )


# ---------------------------------------------------------------------------
# Tests: canonical SOFI scenario — micro present, config requested, not required
# ---------------------------------------------------------------------------

class TestCanonicalSofiScenario:
    """
    Verified SOFI runtime result from CLAUDE.md:
      config.micro = "5M", require_micro_confirmation = False
      phase2.micro present = True
      → micro_state = AVAILABLE_NOT_USED
    """

    def _run_full_chain(self):
        config = SignalEngineConfig(
            micro_context_requested=True,
            require_micro_confirmation=False,
        )
        signal_input = _build_signal_input(include_micro=True)
        signal_result = SignalEngine(config).evaluate(signal_input)

        signal_id = uuid.uuid4()
        trade_plan_result = TradePlanEngine().build_plan(
            TradePlanEngineInput(
                signal_id=signal_id,
                signal_result=signal_result,
                signal_source=signal_input,
            )
        )
        workflow_result = AlertWorkflow(AlertWorkflowConfig()).evaluate(
            AlertWorkflowInput(
                signal_id=signal_id,
                signal_result=signal_result,
                trade_plan_result=trade_plan_result,
                prior_alert_state=None,
                snapshot_request_config=None,
            )
        )
        rendered = TelegramRenderer().render(workflow_result.payload)
        return signal_result, workflow_result, rendered

    def test_signal_engine_produces_long(self):
        signal_result, _, _ = self._run_full_chain()
        assert signal_result.signal == "LONG"

    def test_signal_engine_grade_is_sendable(self):
        signal_result, _, _ = self._run_full_chain()
        assert signal_result.grade in {"A+", "A"}

    def test_signal_engine_micro_state_is_available_not_used(self):
        signal_result, _, _ = self._run_full_chain()
        assert signal_result.extensible_context["micro_state"] == "AVAILABLE_NOT_USED"

    def test_signal_engine_micro_present_is_true(self):
        signal_result, _, _ = self._run_full_chain()
        assert signal_result.extensible_context["micro_present"] is True

    def test_signal_engine_micro_used_for_confirmation_is_false(self):
        signal_result, _, _ = self._run_full_chain()
        assert signal_result.extensible_context["micro_used_for_confirmation"] is False

    def test_alert_workflow_sends(self):
        _, workflow_result, _ = self._run_full_chain()
        assert workflow_result.send is True

    def test_alert_payload_micro_state_propagated(self):
        _, workflow_result, _ = self._run_full_chain()
        assert workflow_result.payload.micro_state == "AVAILABLE_NOT_USED"

    def test_alert_payload_micro_present_propagated(self):
        _, workflow_result, _ = self._run_full_chain()
        assert workflow_result.payload.micro_present is True

    def test_alert_payload_micro_trigger_state_propagated(self):
        _, workflow_result, _ = self._run_full_chain()
        assert workflow_result.payload.micro_trigger_state == "LTF_BULLISH_RECLAIM"

    def test_alert_payload_micro_used_for_confirmation_propagated(self):
        _, workflow_result, _ = self._run_full_chain()
        assert workflow_result.payload.micro_used_for_confirmation is False

    def test_rendered_text_contains_micro_state(self):
        _, _, rendered = self._run_full_chain()
        assert "AVAILABLE_NOT_USED" in rendered.text

    def test_rendered_text_contains_micro_present_true(self):
        _, _, rendered = self._run_full_chain()
        assert "present=True" in rendered.text

    def test_rendered_text_contains_trigger_state(self):
        _, _, rendered = self._run_full_chain()
        assert "LTF_BULLISH_RECLAIM" in rendered.text

    def test_rendered_text_contains_used_for_confirmation_false(self):
        _, _, rendered = self._run_full_chain()
        assert "used_for_confirmation=False" in rendered.text

    def test_rendered_text_contains_delayed_data_disclaimer(self):
        _, _, rendered = self._run_full_chain()
        assert "Polygon delayed 15m" in rendered.text


# ---------------------------------------------------------------------------
# Tests: micro requested but unavailable → REQUESTED_UNAVAILABLE
# ---------------------------------------------------------------------------

class TestMicroRequestedUnavailable:
    """
    When micro context is requested (timeframes.micro = "5M") but
    the DB returned no 5M rows, DbPhase2FeatureLoader returns None and
    the runner skips the symbol. Testing the signal engine path directly:
    set micro_context_requested=True but pass micro=None in the input.
    """

    def _run(self):
        config = SignalEngineConfig(
            micro_context_requested=True,
            require_micro_confirmation=False,
        )
        return SignalEngine(config).evaluate(_build_signal_input(include_micro=False))

    def test_micro_state_is_requested_unavailable(self):
        assert self._run().extensible_context["micro_state"] == "REQUESTED_UNAVAILABLE"

    def test_micro_present_is_false(self):
        assert self._run().extensible_context["micro_present"] is False


# ---------------------------------------------------------------------------
# Tests: micro not requested at all → NOT_REQUESTED
# ---------------------------------------------------------------------------

class TestMicroNotRequested:
    """
    When config does not request micro (timeframes.micro = None and
    require_micro_confirmation = False), micro_state = NOT_REQUESTED
    regardless of whether 5M data exists.
    """

    def _run(self):
        config = SignalEngineConfig(
            micro_context_requested=False,
            require_micro_confirmation=False,
        )
        return SignalEngine(config).evaluate(_build_signal_input(include_micro=False))

    def test_micro_state_is_not_requested(self):
        assert self._run().extensible_context["micro_state"] == "NOT_REQUESTED"

    def test_micro_present_is_false(self):
        assert self._run().extensible_context["micro_present"] is False
