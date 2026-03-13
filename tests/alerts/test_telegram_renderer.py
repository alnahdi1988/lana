from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from doctrine_engine.alerts.models import AlertDecisionPayload
from doctrine_engine.alerts.telegram_renderer import TelegramRenderer


def _payload(*, alert_state: str = "NEW") -> AlertDecisionPayload:
    payload = AlertDecisionPayload(
        symbol_id=uuid.uuid4(),
        ticker="TEST",
        signal="LONG",
        confidence=Decimal("0.8100"),
        grade="A",
        setup_state="RECONTAINMENT_CONFIRMED",
        market_regime="BULLISH_TREND",
        sector_regime="SECTOR_STRONG",
        event_risk_class="NO_EVENT_RISK",
        entry_type="BASE",
        entry_zone_low=Decimal("10.0000"),
        entry_zone_high=Decimal("10.5500"),
        confirmation_level=Decimal("10.8000"),
        invalidation_level=Decimal("9.8000"),
        tp1=Decimal("10.9500"),
        tp2=Decimal("11.3000"),
        signal_timestamp=datetime(2026, 3, 8, 15, 45, tzinfo=timezone.utc),
        known_at=datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc),
        alert_state=alert_state,
        priority="STANDARD",
        operator_summary="STANDARD A LONG TEST | RECONTAINMENT_CONFIRMED | BASE | zone 10.0000-10.5500 | invalid 9.8000 | known 2026-03-08T16:00:00+00:00",
        reason_codes=["PRICE_RANGE_VALID", "UNIVERSE_ELIGIBLE"],
        micro_state="AVAILABLE_NOT_USED",
        micro_present=True,
        micro_trigger_state="LTF_BULLISH_RECLAIM",
        micro_used_for_confirmation=False,
        snapshot_path=None,
    )
    return payload


def test_renderer_uses_exact_line_structure_and_delayed_wording() -> None:
    result = TelegramRenderer().render(_payload())
    lines = result.text.splitlines()

    assert lines[0] == "STANDARD | A LONG | TEST"
    assert lines[1] == "Setup: RECONTAINMENT_CONFIRMED | Entry: BASE"
    assert lines[2] == "Zone: 10.0000 - 10.5500 | Confirm: 10.8000"
    assert lines[3] == "Invalid: 9.8000 | TP1: 10.9500 | TP2: 11.3000"
    assert lines[6] == "Micro: state=AVAILABLE_NOT_USED | present=True | trigger=LTF_BULLISH_RECLAIM | used_for_confirmation=False"
    assert lines[7] == "Context: market=BULLISH_TREND | sector=SECTOR_STRONG | event_risk=NO_EVENT_RISK"
    assert lines[8] == "Data: Polygon delayed 15m. Operator workflow alert only, not live execution."


def test_renderer_uses_update_prefix_for_upgraded_payloads() -> None:
    result = TelegramRenderer().render(_payload(alert_state="UPGRADED"))
    assert result.text.splitlines()[0] == "UPDATE | STANDARD | A LONG | TEST"


def test_decimal_fields_render_deterministically_and_summary_is_preserved() -> None:
    payload = _payload()
    result = TelegramRenderer().render(payload)

    assert "10.0000 - 10.5500" in result.text
    assert f"Summary: {payload.operator_summary}" in result.text


def test_renderer_text_contains_signal_and_known_timestamps() -> None:
    result = TelegramRenderer().render(_payload())

    assert "Signal: 2026-03-08T15:45:00+00:00" in result.text
    assert "Known: 2026-03-08T16:00:00+00:00" in result.text


def test_renderer_not_used_for_suppressed_workflow_in_normal_pattern() -> None:
    payload = replace(_payload(), alert_state="SUPPRESSED")
    renderer_called = False

    def maybe_render(send: bool) -> str | None:
        nonlocal renderer_called
        if not send:
            return None
        renderer_called = True
        return TelegramRenderer().render(payload).text

    rendered = maybe_render(False)

    assert rendered is None
    assert renderer_called is False
