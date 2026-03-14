from __future__ import annotations

from pathlib import Path

from doctrine_engine.product import operator_config


def test_operator_settings_round_trip_and_setup_completion(tmp_path, monkeypatch):
    doctrine_home = tmp_path / ".doctrine"
    monkeypatch.setattr(operator_config, "DOCTRINE_HOME", doctrine_home)
    monkeypatch.setattr(operator_config, "OPERATOR_SETTINGS_PATH", doctrine_home / "operator_settings.json")
    monkeypatch.setattr(operator_config, "DEFAULT_OPERATOR_STATE_DB_PATH", str((doctrine_home / "operations.db").resolve()))

    settings_payload = {
        "database_url": "sqlite:///operator.db",
        "polygon_api_key": "polygon-key",
        "telegram_enabled": True,
        "telegram_bot_token": "bot-token",
        "telegram_chat_id": "chat-id",
        "run_interval_seconds": 600,
        "auto_start_runtime": True,
        "delayed_data_wording_mode": "strict",
        "operator_state_db_path": str(doctrine_home / "operations.db"),
    }
    validation = {
        "database": {"ok": True, "message": "db ok"},
        "ops_store": {"ok": True, "message": "ops ok"},
        "polygon": {"ok": True, "message": "polygon ok"},
        "telegram": {"ok": True, "message": "telegram ok", "status": "SENT", "message_id": "12"},
    }

    operator_config.save_operator_settings_document(settings_payload, validation=validation)
    document = operator_config.load_operator_settings_document()

    assert document["settings"]["run_interval_seconds"] == 600
    assert document["settings"]["delayed_data_wording_mode"] == "strict"
    assert operator_config.setup_is_complete(document) is True


def test_validate_operator_settings_uses_real_sqlite_and_mocked_telegram(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "doctrine_engine.product.operator_config.TelegramTransport.send_message",
        lambda self, text: type(
            "Result",
            (),
            {"status": "SENT", "message_id": "55", "error_message": None, "sent_at": None},
        )(),
    )
    payload = {
        "database_url": "sqlite://",
        "polygon_api_key": "polygon-key",
        "telegram_enabled": True,
        "telegram_bot_token": "token",
        "telegram_chat_id": "chat",
        "run_interval_seconds": 900,
        "auto_start_runtime": False,
        "delayed_data_wording_mode": "standard",
        "operator_state_db_path": str(tmp_path / "ops.db"),
    }

    result = operator_config.validate_operator_settings(
        payload,
        send_telegram_test=True,
        telegram_label="TEST",
    )

    assert result.ok is True
    assert result.details["database"]["ok"] is True
    assert result.details["ops_store"]["ok"] is True
    assert result.details["telegram"]["status"] == "SENT"
