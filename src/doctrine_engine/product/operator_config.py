from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from doctrine_engine.product.clients import TelegramSendResult, TelegramTransport

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCTRINE_HOME = REPO_ROOT / ".doctrine"
OPERATOR_SETTINGS_PATH = DOCTRINE_HOME / "operator_settings.json"
DEFAULT_OPERATOR_STATE_DB_PATH = str((DOCTRINE_HOME / "operations.db").resolve())
DELAYED_DATA_WORDING_MODES = {"standard", "strict"}
OPERATOR_MANAGED_FIELDS = {
    "paper_trading_mode",
    "database_url",
    "polygon_api_key",
    "telegram_enabled",
    "telegram_bot_token",
    "telegram_chat_id",
    "run_interval_seconds",
    "auto_start_runtime",
    "delayed_data_wording_mode",
    "operator_state_db_path",
}
RUNTIME_RESTART_FIELDS = {
    "database_url",
    "polygon_api_key",
    "telegram_enabled",
    "telegram_bot_token",
    "telegram_chat_id",
    "run_interval_seconds",
    "delayed_data_wording_mode",
    "operator_state_db_path",
}


@dataclass(frozen=True, slots=True)
class OperatorSettingsValidation:
    ok: bool
    details: dict[str, Any]


def get_operator_settings_path() -> Path:
    DOCTRINE_HOME.mkdir(parents=True, exist_ok=True)
    return OPERATOR_SETTINGS_PATH


def default_operator_settings() -> dict[str, Any]:
    return {
        "paper_trading_mode": True,
        "database_url": "",
        "polygon_api_key": "",
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "run_interval_seconds": 900,
        "auto_start_runtime": False,
        "delayed_data_wording_mode": "standard",
        "operator_state_db_path": DEFAULT_OPERATOR_STATE_DB_PATH,
    }


def load_operator_settings_document() -> dict[str, Any]:
    path = get_operator_settings_path()
    if not path.exists():
        return {"settings": default_operator_settings(), "meta": {"validated_at": None, "validation": {}}}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"settings": default_operator_settings(), "meta": {"validated_at": None, "validation": {}}}
    payload = json.loads(raw)
    settings = default_operator_settings()
    settings.update({key: payload.get("settings", {}).get(key, settings[key]) for key in settings})
    meta = payload.get("meta") or {}
    return {
        "settings": settings,
        "meta": {
            "validated_at": meta.get("validated_at"),
            "validation": meta.get("validation") or {},
        },
    }


def load_operator_settings_overrides() -> dict[str, Any]:
    path = get_operator_settings_path()
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return dict(load_operator_settings_document()["settings"])


def save_operator_settings_document(
    settings_payload: dict[str, Any],
    *,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = get_operator_settings_path()
    document = {
        "settings": _normalized_settings(settings_payload),
        "meta": {
            "validated_at": datetime.now(timezone.utc).isoformat() if validation else None,
            "validation": validation or {},
        },
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return document


def merge_operator_settings(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(_normalized_settings(updates))
    return merged


def restart_required_keys(existing: dict[str, Any], updated: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for key in sorted(RUNTIME_RESTART_FIELDS):
        if existing.get(key) != updated.get(key):
            changed.append(key)
    return changed


def setup_is_complete(document: dict[str, Any]) -> bool:
    validation = document.get("meta", {}).get("validation") or {}
    settings = document.get("settings") or {}
    if not settings.get("database_url"):
        return False
    if not settings.get("polygon_api_key"):
        return False
    if not settings.get("operator_state_db_path"):
        return False
    if validation.get("database", {}).get("ok") is not True:
        return False
    if validation.get("ops_store", {}).get("ok") is not True:
        return False
    if settings.get("telegram_enabled"):
        return validation.get("telegram", {}).get("ok") is True
    return True


def build_operator_settings_view(current_settings: Any) -> dict[str, Any]:
    document = load_operator_settings_document()
    settings = dict(document["settings"])
    for key in OPERATOR_MANAGED_FIELDS:
        if hasattr(current_settings, key):
            settings[key] = getattr(current_settings, key)
    settings["signal_send_threshold_mode"] = "workflow-controlled"
    settings["operator_settings_path"] = str(get_operator_settings_path())
    settings["setup_complete"] = setup_is_complete(document) or effective_settings_complete(settings)
    settings["validation"] = document.get("meta", {}).get("validation") or {}
    settings["validated_at"] = document.get("meta", {}).get("validated_at")
    return settings


def validate_operator_settings(
    settings_payload: dict[str, Any],
    *,
    send_telegram_test: bool,
    telegram_label: str,
) -> OperatorSettingsValidation:
    normalized = _normalized_settings(settings_payload)
    validation: dict[str, Any] = {
        "database": _validate_database(normalized["database_url"]),
        "ops_store": _validate_ops_store(normalized["operator_state_db_path"]),
    }
    validation["polygon"] = {
        "ok": bool(normalized["polygon_api_key"]),
        "message": "Configured." if normalized["polygon_api_key"] else "Polygon API key is required.",
    }
    if normalized["telegram_enabled"]:
        validation["telegram"] = _validate_telegram(
            enabled=True,
            bot_token=normalized["telegram_bot_token"],
            chat_id=normalized["telegram_chat_id"],
            send_message=send_telegram_test,
            label=telegram_label,
        )
    else:
        validation["telegram"] = {
            "ok": True,
            "message": "Telegram disabled by operator setting.",
            "status": "SKIPPED_DISABLED",
            "message_id": None,
        }
    return OperatorSettingsValidation(
        ok=all(item.get("ok") is True for item in validation.values()),
        details=validation,
    )


def effective_settings_complete(settings_payload: dict[str, Any]) -> bool:
    if not settings_payload.get("database_url"):
        return False
    if not settings_payload.get("polygon_api_key"):
        return False
    if not settings_payload.get("operator_state_db_path"):
        return False
    if settings_payload.get("telegram_enabled") and (
        not settings_payload.get("telegram_bot_token") or not settings_payload.get("telegram_chat_id")
    ):
        return False
    return True


def _normalized_settings(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = default_operator_settings()
    normalized = dict(defaults)
    for key in defaults:
        if key not in payload:
            continue
        value = payload[key]
        if key in {"telegram_enabled", "auto_start_runtime", "paper_trading_mode"}:
            normalized[key] = _as_bool(value)
        elif key == "run_interval_seconds":
            normalized[key] = max(int(value or defaults[key]), 60)
        elif key == "delayed_data_wording_mode":
            mode = str(value or defaults[key]).strip().lower()
            normalized[key] = mode if mode in DELAYED_DATA_WORDING_MODES else defaults[key]
        elif key == "operator_state_db_path":
            normalized[key] = str(_resolve_local_path(str(value or defaults[key])))
        else:
            normalized[key] = str(value or "").strip()
    normalized["paper_trading_mode"] = True
    return normalized


def _validate_database(database_url: str) -> dict[str, Any]:
    if not database_url:
        return {"ok": False, "message": "Database URL is required."}
    try:
        engine = create_engine(database_url, future=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": "Database connection succeeded."}


def _validate_ops_store(path_value: str) -> dict[str, Any]:
    try:
        path = _resolve_local_path(path_value)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8"):
            pass
    except Exception as exc:
        return {"ok": False, "message": str(exc), "path": str(path_value)}
    return {"ok": True, "message": "Ops store path is writable.", "path": str(path)}


def _validate_telegram(
    *,
    enabled: bool,
    bot_token: str,
    chat_id: str,
    send_message: bool,
    label: str,
) -> dict[str, Any]:
    transport = TelegramTransport(
        enabled=enabled,
        bot_token=bot_token or None,
        chat_id=chat_id or None,
    )
    result = transport.send_message(label) if send_message else TelegramSendResult(
        status="SKIPPED_DISABLED",
        message_id=None,
        error_message="Telegram validation send disabled.",
        sent_at=None,
    )
    return {
        "ok": result.status == "SENT",
        "message": result.error_message or ("Telegram connectivity succeeded." if result.status == "SENT" else result.status),
        "status": result.status,
        "message_id": result.message_id,
    }


def _resolve_local_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "DEFAULT_OPERATOR_STATE_DB_PATH",
    "DOCTRINE_HOME",
    "OPERATOR_MANAGED_FIELDS",
    "OPERATOR_SETTINGS_PATH",
    "OperatorSettingsValidation",
    "build_operator_settings_view",
    "default_operator_settings",
    "effective_settings_complete",
    "get_operator_settings_path",
    "load_operator_settings_document",
    "load_operator_settings_overrides",
    "merge_operator_settings",
    "restart_required_keys",
    "save_operator_settings_document",
    "setup_is_complete",
    "validate_operator_settings",
]
