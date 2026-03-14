from __future__ import annotations

from decimal import Decimal

from doctrine_engine.alerts.models import AlertDecisionPayload, TelegramRenderResult


class TelegramRenderer:
    def __init__(self, *, delayed_data_wording_mode: str = "standard") -> None:
        self.delayed_data_wording_mode = delayed_data_wording_mode

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
                (
                    "Micro: "
                    f"state={payload.micro_state} | "
                    f"present={payload.micro_present} | "
                    f"trigger={payload.micro_trigger_state or 'NONE'} | "
                    f"used_for_confirmation={payload.micro_used_for_confirmation}"
                ),
                (
                    "Context: "
                    f"market={payload.market_regime or 'UNKNOWN'} | "
                    f"sector={payload.sector_regime or 'UNKNOWN'} | "
                    f"event_risk={payload.event_risk_class or 'UNKNOWN'}"
                ),
                f"Data: {self._delayed_data_line()}",
                f"Summary: {payload.operator_summary}",
                f"Reasons: {', '.join(payload.reason_codes)}",
            ]
        )
        return TelegramRenderResult(text=text)

    def _decimal_text(self, value: Decimal) -> str:
        return format(value, "f")

    def _delayed_data_line(self) -> str:
        if self.delayed_data_wording_mode == "strict":
            return "Polygon delayed 15m. Manual review only. Do not treat this as a live execution trigger."
        return "Polygon delayed 15m. Operator workflow alert only, not live execution."
