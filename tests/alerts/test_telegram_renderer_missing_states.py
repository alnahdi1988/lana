"""
tests/alerts/test_telegram_renderer_missing_states.py

Missing coverage identified by micro-state audit.
Tests TelegramRenderer with micro_state=NOT_REQUESTED and REQUESTED_UNAVAILABLE.
These states are not covered in the existing test_telegram_renderer.py.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from doctrine_engine.alerts.telegram_renderer import TelegramRenderer
from doctrine_engine.alerts.models import AlertDecisionPayload


# ---------------------------------------------------------------------------
# Helpers — build minimal AlertDecisionPayload for renderer tests
# ---------------------------------------------------------------------------

def make_payload(**micro_overrides):
    """
    Build a minimal AlertDecisionPayload with micro fields overridden.
    """
    base = dict(
        symbol_id=uuid.UUID("319f2af7-6084-4a5b-af82-b8ca500bb891"),
        ticker="TEST",
        signal="LONG",
        confidence=Decimal("0.7500"),
        grade="B",
        setup_state="RECONTAINMENT_CONFIRMED",
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5500"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("10.9500"),
        tp2=Decimal("11.3000"),
        signal_timestamp=datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc),
        alert_state="NEW",
        priority="STANDARD",
        operator_summary="STANDARD B LONG TEST | RECONTAINMENT_CONFIRMED | BASE | zone 10.0000-10.5500 | invalid 9.8000 | known 2026-03-08T16:00:00+00:00",
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        micro_state="NOT_REQUESTED",
        micro_present=False,
        micro_trigger_state=None,
        micro_used_for_confirmation=False,
        snapshot_path=None,
    )
    base.update(micro_overrides)
    return AlertDecisionPayload(**base)


# ---------------------------------------------------------------------------
# Test: NOT_REQUESTED
# ---------------------------------------------------------------------------

class TestRendererMicroNotRequested:
    """
    When micro was never requested (config did not set timeframes.micro),
    the renderer must surface micro_state=NOT_REQUESTED without crashing.
    """

    def test_render_includes_micro_line(self):
        payload = make_payload(
            micro_state="NOT_REQUESTED",
            micro_present=False,
            micro_trigger_state=None,
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        text = renderer.render(payload).text

        assert "NOT_REQUESTED" in text, (
            "Rendered text must include micro_state=NOT_REQUESTED"
        )

    def test_render_does_not_crash(self):
        payload = make_payload(
            micro_state="NOT_REQUESTED",
            micro_present=False,
            micro_trigger_state=None,
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        result = renderer.render(payload)
        assert isinstance(result.text, str)
        assert len(result.text) > 0


# ---------------------------------------------------------------------------
# Test: REQUESTED_UNAVAILABLE
# ---------------------------------------------------------------------------

class TestRendererMicroRequestedUnavailable:
    """
    When micro was requested but DB had no rows,
    the renderer must surface micro_state=REQUESTED_UNAVAILABLE.
    """

    def test_render_includes_micro_line(self):
        payload = make_payload(
            micro_state="REQUESTED_UNAVAILABLE",
            micro_present=False,
            micro_trigger_state=None,
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        text = renderer.render(payload).text

        assert "REQUESTED_UNAVAILABLE" in text, (
            "Rendered text must include micro_state=REQUESTED_UNAVAILABLE"
        )

    def test_render_micro_present_is_false(self):
        payload = make_payload(
            micro_state="REQUESTED_UNAVAILABLE",
            micro_present=False,
            micro_trigger_state=None,
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        text = renderer.render(payload).text

        assert "present=False" in text, (
            "Rendered text must show present=False for REQUESTED_UNAVAILABLE"
        )

    def test_render_does_not_crash(self):
        payload = make_payload(
            micro_state="REQUESTED_UNAVAILABLE",
            micro_present=False,
            micro_trigger_state=None,
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        result = renderer.render(payload)
        assert isinstance(result.text, str)
        assert len(result.text) > 0


# ---------------------------------------------------------------------------
# Regression: AVAILABLE_NOT_USED still works (canonical SOFI fixture)
# ---------------------------------------------------------------------------

class TestRendererMicroAvailableNotUsed:
    """
    Regression guard for the verified SOFI runtime result.
    This state was the original fix — must never regress.
    """

    def test_sofi_canonical_output(self):
        payload = make_payload(
            micro_state="AVAILABLE_NOT_USED",
            micro_present=True,
            micro_trigger_state="LTF_BULLISH_RECLAIM",
            micro_used_for_confirmation=False,
        )
        renderer = TelegramRenderer()
        text = renderer.render(payload).text

        assert "AVAILABLE_NOT_USED" in text
        assert "present=True" in text
        assert "LTF_BULLISH_RECLAIM" in text
        assert "used_for_confirmation=False" in text
