from __future__ import annotations

import json
from datetime import timezone

from doctrine_engine.product.clients import TelegramTransport


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_telegram_transport_success(monkeypatch):
    monkeypatch.setattr(
        "doctrine_engine.product.clients.urlopen",
        lambda request, timeout: _FakeResponse({"ok": True, "result": {"message_id": 42}}),
    )
    transport = TelegramTransport(enabled=True, bot_token="token", chat_id="chat")
    result = transport.send_message("hello")
    assert result.status == "SENT"
    assert result.message_id == "42"
    assert result.sent_at is not None
    assert result.sent_at.tzinfo == timezone.utc


def test_telegram_transport_disabled():
    transport = TelegramTransport(enabled=False, bot_token=None, chat_id=None)
    result = transport.send_message("hello")
    assert result.status == "SKIPPED_DISABLED"

