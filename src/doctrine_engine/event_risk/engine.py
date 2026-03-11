from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from doctrine_engine.event_risk.models import (
    EventRiskEngineConfig,
    EventRiskEngineInput,
    EventRiskEngineResult,
)


class EventRiskEngine:
    def __init__(self, config: EventRiskEngineConfig | None = None) -> None:
        self.config = config or EventRiskEngineConfig()

    def evaluate(self, event_risk_input: EventRiskEngineInput) -> EventRiskEngineResult:
        self._validate_input(event_risk_input)

        coverage_complete = (
            event_risk_input.earnings is not None
            and event_risk_input.corporate_events is not None
            and event_risk_input.news_risks is not None
            and event_risk_input.halt_risk is not None
        )

        earnings = self._consumed_earnings(event_risk_input)
        corporate_events = self._consumed_corporate_events(event_risk_input)
        news_risks = self._consumed_news_risks(event_risk_input)
        halt_risk = self._consumed_halt_risk(event_risk_input)

        known_at_candidates = [event_risk_input.known_at]
        if earnings is not None:
            known_at_candidates.append(earnings.known_at)
        known_at_candidates.extend(event.known_at for event in corporate_events)
        known_at_candidates.extend(news.known_at for news in news_risks)
        if halt_risk is not None:
            known_at_candidates.append(halt_risk.known_at)
        known_at = max(known_at_candidates)

        reason_codes: list[str]
        event_risk_class: str
        blocked: bool
        soft_penalty = Decimal("0.0000")

        if self._halt_block_active(event_risk_input, halt_risk):
            event_risk_class = "HALT_RISK"
            blocked = True
            reason_codes = ["HALT_RISK_BLOCKED"]
        elif self._earnings_block_active(event_risk_input, earnings):
            event_risk_class = "EARNINGS_BLOCK"
            blocked = True
            reason_codes = ["EARNINGS_BLACKOUT_ACTIVE"]
        elif self._corporate_block_active(event_risk_input, corporate_events):
            event_risk_class = "CORPORATE_EVENT_BLOCK"
            blocked = True
            reason_codes = ["CORPORATE_EVENT_BLOCKED"]
        else:
            reason_codes = []
            if any(news.category == "ABNORMAL_VOLUME_NEWS" for news in news_risks):
                reason_codes.append("ABNORMAL_VOLUME_NEWS")
                soft_penalty += self.config.abnormal_news_soft_penalty
            if any(news.category == "UNCLEAR_BINARY_NEWS" for news in news_risks):
                reason_codes.append("UNCLEAR_BINARY_NEWS")
                soft_penalty += self.config.unclear_news_soft_penalty
            soft_penalty = min(self.config.max_soft_penalty, soft_penalty).quantize(Decimal("0.0000"))
            if reason_codes:
                event_risk_class = "NEWS_ABNORMAL_RISK"
                blocked = False
            else:
                event_risk_class = "NO_EVENT_RISK"
                blocked = False
                reason_codes = ["EVENT_RISK_CLEAR"]

        if not coverage_complete:
            reason_codes.append("EVENT_RISK_PARTIAL_COVERAGE")

        return EventRiskEngineResult(
            config_version=self.config.config_version,
            event_risk_class=event_risk_class,
            blocked=blocked,
            coverage_complete=coverage_complete,
            soft_penalty=Decimal("0.0000") if blocked else soft_penalty,
            reason_codes=reason_codes,
            known_at=known_at,
            extensible_context={
                "earnings_snapshot": {
                    "earnings_datetime": earnings.earnings_datetime.isoformat() if earnings is not None and earnings.earnings_datetime is not None else None,
                    "known_at": earnings.known_at.isoformat() if earnings is not None else None,
                    "source": earnings.source if earnings is not None else None,
                },
                "corporate_event_snapshot": [
                    {
                        "event_type": event.event_type,
                        "event_datetime": event.event_datetime.isoformat(),
                        "known_at": event.known_at.isoformat(),
                        "blocks_longs": event.blocks_longs,
                        "source": event.source,
                    }
                    for event in corporate_events
                ],
                "news_snapshot": [
                    {
                        "category": news.category,
                        "event_datetime": news.event_datetime.isoformat(),
                        "known_at": news.known_at.isoformat(),
                        "severity_score": format(news.severity_score, "f"),
                        "source": news.source,
                    }
                    for news in news_risks
                ],
                "halt_snapshot": {
                    "halt_detected": halt_risk.halt_detected if halt_risk is not None else None,
                    "halt_datetime": halt_risk.halt_datetime.isoformat() if halt_risk is not None and halt_risk.halt_datetime is not None else None,
                    "known_at": halt_risk.known_at.isoformat() if halt_risk is not None else None,
                    "source": halt_risk.source if halt_risk is not None else None,
                },
            },
        )

    def _validate_input(self, event_risk_input: EventRiskEngineInput) -> None:
        if event_risk_input.earnings is not None and event_risk_input.earnings.known_at > event_risk_input.known_at:
            raise ValueError("Earnings input cannot be known after event-risk baseline known_at.")
        for event in event_risk_input.corporate_events or []:
            if event.known_at > event_risk_input.known_at:
                raise ValueError("Corporate event input cannot be known after event-risk baseline known_at.")
        for news in event_risk_input.news_risks or []:
            if news.known_at > event_risk_input.known_at:
                raise ValueError("News risk input cannot be known after event-risk baseline known_at.")
            if news.severity_score < Decimal("0"):
                raise ValueError("News severity_score cannot be negative.")
        if event_risk_input.halt_risk is not None and event_risk_input.halt_risk.known_at > event_risk_input.known_at:
            raise ValueError("Halt risk input cannot be known after event-risk baseline known_at.")

    def _consumed_earnings(self, event_risk_input: EventRiskEngineInput):
        earnings = event_risk_input.earnings
        if earnings is None or earnings.known_at > event_risk_input.known_at:
            return None
        return earnings

    def _consumed_corporate_events(self, event_risk_input: EventRiskEngineInput):
        return [
            event
            for event in (event_risk_input.corporate_events or [])
            if event.known_at <= event_risk_input.known_at
        ]

    def _consumed_news_risks(self, event_risk_input: EventRiskEngineInput):
        return [
            news
            for news in (event_risk_input.news_risks or [])
            if news.known_at <= event_risk_input.known_at
        ]

    def _consumed_halt_risk(self, event_risk_input: EventRiskEngineInput):
        halt_risk = event_risk_input.halt_risk
        if halt_risk is None or halt_risk.known_at > event_risk_input.known_at:
            return None
        return halt_risk

    def _earnings_block_active(self, event_risk_input: EventRiskEngineInput, earnings) -> bool:
        if earnings is None or earnings.earnings_datetime is None:
            return False
        start = earnings.earnings_datetime - timedelta(days=self.config.earnings_block_days_before)
        end = earnings.earnings_datetime + timedelta(days=self.config.earnings_block_days_after)
        return start <= event_risk_input.signal_timestamp <= end

    def _corporate_block_active(self, event_risk_input: EventRiskEngineInput, corporate_events) -> bool:
        for event in corporate_events:
            if not event.blocks_longs:
                continue
            end = event.event_datetime + timedelta(days=self.config.corporate_block_days_after)
            if event.event_datetime <= event_risk_input.signal_timestamp <= end:
                return True
        return False

    def _halt_block_active(self, event_risk_input: EventRiskEngineInput, halt_risk) -> bool:
        if halt_risk is None or not halt_risk.halt_detected or halt_risk.halt_datetime is None:
            return False
        end = halt_risk.halt_datetime + timedelta(days=self.config.halt_block_days_after)
        return halt_risk.halt_datetime <= event_risk_input.signal_timestamp <= end
