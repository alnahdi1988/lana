from __future__ import annotations

from decimal import Decimal

from doctrine_engine.alerts.models import AlertDecisionPayload, TelegramRenderResult


class TelegramRenderer:
    def render(self, payload: AlertDecisionPayload) -> TelegramRenderResult:
        prefix = "UPDATE | " if payload.alert_state == "UPGRADED" else ""
        text = "\n".join(
            [
                f"{prefix}{payload.priority} | {payload.grade} LONG | {payload.ticker}",
                f"Setup: {payload.setup_state} | Entry: {payload.entry_type}",
                (
                    "Zone: "
                    f"{self._decimal_text(payload.entry_zone_low)} - {self._decimal_text(payload.entry_zone_high)}"
                    f" | Confirm: {self._decimal_text(payload.confirmation_level)}"
                ),
                (
                    f"Invalid: {self._decimal_text(payload.invalidation_level)} | "
                    f"TP1: {self._decimal_text(payload.tp1)} | "
                    f"TP2: {self._decimal_text(payload.tp2)}"
                ),
                f"Signal: {payload.signal_timestamp.isoformat()}",
                f"Known: {payload.known_at.isoformat()}",
                "Data: Polygon delayed 15m. Operator workflow alert only, not live execution.",
                f"Summary: {payload.operator_summary}",
                f"Reasons: {', '.join(payload.reason_codes)}",
            ]
        )
        return TelegramRenderResult(text=text)

    def _decimal_text(self, value: Decimal) -> str:
        return format(value, "f")
