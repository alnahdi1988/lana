from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen


class PolygonApiError(RuntimeError):
    pass


class TelegramTransportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramSendResult:
    status: str
    message_id: str | None
    error_message: str | None
    sent_at: datetime | None


class PolygonClient:
    def __init__(self, *, api_key: str, base_url: str, timeout_seconds: int) -> None:
        if not api_key:
            raise ValueError("Polygon API key is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_grouped_daily(self, session_date: date) -> list[dict]:
        payload = self._request_json(f"/v2/aggs/grouped/locale/us/market/stocks/{session_date.isoformat()}")
        return list(payload.get("results") or [])

    def get_ticker_details(self, ticker: str) -> dict:
        payload = self._request_json(f"/v3/reference/tickers/{ticker}")
        return dict(payload.get("results") or {})

    def get_aggs(
        self,
        *,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50_000,
    ) -> list[dict]:
        payload = self._request_json(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date.isoformat()}/{to_date.isoformat()}",
            {
                "adjusted": "true" if adjusted else "false",
                "sort": sort,
                "limit": str(limit),
            },
        )
        return list(payload.get("results") or [])

    def get_news(
        self,
        *,
        ticker: str,
        published_gte: datetime,
        published_lte: datetime,
        limit: int,
    ) -> list[dict]:
        payload = self._request_json(
            "/v2/reference/news",
            {
                "ticker": ticker,
                "published_utc.gte": published_gte.isoformat(),
                "published_utc.lte": published_lte.isoformat(),
                "limit": str(limit),
                "sort": "published_utc",
                "order": "desc",
            },
        )
        return list(payload.get("results") or [])

    def get_earnings(
        self,
        *,
        ticker: str,
        date_gte: date,
        date_lte: date,
        limit: int = 10,
    ) -> list[dict]:
        payload = self._request_json(
            "/benzinga/v1/earnings",
            {
                "ticker": ticker,
                "date.gte": date_gte.isoformat(),
                "date.lte": date_lte.isoformat(),
                "limit": str(limit),
                "sort": "date",
                "order": "asc",
            },
        )
        return list(payload.get("results") or [])

    def _request_json(self, path: str, params: dict[str, str] | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        url = self._with_api_key(url)
        request = Request(url, headers={"User-Agent": "structure-doctrine-engine/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - exercised through tests with patched clients
            raise PolygonApiError(f"Polygon request failed: {exc}") from exc
        status = payload.get("status")
        if status not in {None, "OK"}:
            raise PolygonApiError(f"Polygon request returned status={status!r}: {payload}")
        return payload

    def _with_api_key(self, url: str) -> str:
        parsed = urlparse(url)
        query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_items.setdefault("apiKey", self.api_key)
        return urlunparse(parsed._replace(query=urlencode(query_items)))


class TelegramTransport:
    def __init__(
        self,
        *,
        enabled: bool,
        bot_token: str | None,
        chat_id: str | None,
        timeout_seconds: int = 20,
        base_url: str = "https://api.telegram.org",
    ) -> None:
        self.enabled = enabled
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")

    def send_message(self, text: str) -> TelegramSendResult:
        if not self.enabled:
            return TelegramSendResult(
                status="SKIPPED_DISABLED",
                message_id=None,
                error_message=None,
                sent_at=None,
            )
        if not self.bot_token or not self.chat_id:
            return TelegramSendResult(
                status="SKIPPED_UNCONFIGURED",
                message_id=None,
                error_message="Telegram bot token and chat id are required.",
                sent_at=None,
            )

        payload = json.dumps(
            {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/bot{self.bot_token}/sendMessage",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "structure-doctrine-engine/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return TelegramSendResult(
                status="FAILED",
                message_id=None,
                error_message=str(exc),
                sent_at=None,
            )

        if not body.get("ok"):
            return TelegramSendResult(
                status="FAILED",
                message_id=None,
                error_message=str(body.get("description") or "Telegram API returned ok=false."),
                sent_at=None,
            )

        result = body.get("result") or {}
        return TelegramSendResult(
            status="SENT",
            message_id=str(result.get("message_id")) if result.get("message_id") is not None else None,
            error_message=None,
            sent_at=datetime.now(timezone.utc),
        )
