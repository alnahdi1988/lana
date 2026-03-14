from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from doctrine_engine.product import operator_config
from doctrine_engine.product.state import OperationalStateStore
from doctrine_engine.product.web import create_operator_app


def _configure_operator_paths(monkeypatch, tmp_path: Path) -> None:
    doctrine_home = tmp_path / ".doctrine"
    monkeypatch.setattr(operator_config, "DOCTRINE_HOME", doctrine_home)
    monkeypatch.setattr(operator_config, "OPERATOR_SETTINGS_PATH", doctrine_home / "operator_settings.json")
    monkeypatch.setattr(operator_config, "DEFAULT_OPERATOR_STATE_DB_PATH", str((doctrine_home / "operations.db").resolve()))


class _StubController:
    def __init__(self):
        self.actions: list[str] = []

    def status_snapshot(self):
        return {
            "setup_complete": False,
            "dashboard_url": "http://127.0.0.1:8000/",
            "engine": {"state": "STOPPED", "pid": None},
            "web": {"state": "RUNNING", "pid": 100},
            "run_once": {"state": "IDLE"},
        }

    def start_system(self):
        self.actions.append("start")
        return self.status_snapshot()

    def stop_system(self):
        self.actions.append("stop")
        return self.status_snapshot()

    def restart_system(self):
        self.actions.append("restart")
        return self.status_snapshot()

    def run_once_now(self):
        self.actions.append("run_once")
        return self.status_snapshot()

    def open_dashboard(self):
        self.actions.append("open_dashboard")
        return self.status_snapshot()


def test_setup_flow_redirects_and_saves(monkeypatch, tmp_path):
    _configure_operator_paths(monkeypatch, tmp_path)
    validation = {
        "database": {"ok": True, "message": "db ok"},
        "ops_store": {"ok": True, "message": "ops ok"},
        "polygon": {"ok": True, "message": "polygon ok"},
        "telegram": {"ok": True, "message": "telegram ok", "status": "SENT", "message_id": "33"},
    }
    monkeypatch.setattr(
        "doctrine_engine.product.web.validate_operator_settings",
        lambda payload, send_telegram_test, telegram_label: operator_config.OperatorSettingsValidation(ok=True, details=validation),
    )
    current_settings = SimpleNamespace(
        paper_trading_mode=True,
        database_url="",
        polygon_api_key="",
        telegram_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
        run_interval_seconds=900,
        auto_start_runtime=False,
        delayed_data_wording_mode="standard",
        operator_state_db_path=str(tmp_path / "ops.db"),
    )
    controller = _StubController()
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = create_operator_app(
        store,
        controller=controller,
        app_builder=lambda: SimpleNamespace(
            state_store=store,
            send_telegram_test_message=lambda source: None,
        ),
        operator_settings_builder=lambda: operator_config.build_operator_settings_view(current_settings),
        enforce_setup=True,
    )
    client = TestClient(app)

    redirect = client.get("/", follow_redirects=False)
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/setup"

    response = client.post(
        "/setup/save",
        data={
            "database_url": "sqlite://",
            "polygon_api_key": "polygon-key",
            "telegram_enabled": "on",
            "telegram_bot_token": "token",
            "telegram_chat_id": "chat",
            "run_interval_seconds": "900",
            "auto_start_runtime": "on",
            "delayed_data_wording_mode": "strict",
            "operator_state_db_path": str(tmp_path / "ops.db"),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/settings?saved=1"


def test_settings_page_and_telegram_test_send_route(monkeypatch, tmp_path):
    _configure_operator_paths(monkeypatch, tmp_path)
    operator_config.save_operator_settings_document(
        {
            "database_url": "sqlite://",
            "polygon_api_key": "polygon-key",
            "telegram_enabled": True,
            "telegram_bot_token": "token",
            "telegram_chat_id": "chat",
            "run_interval_seconds": 900,
            "auto_start_runtime": False,
            "delayed_data_wording_mode": "standard",
            "operator_state_db_path": str(tmp_path / "ops.db"),
        },
        validation={
            "database": {"ok": True, "message": "db ok"},
            "ops_store": {"ok": True, "message": "ops ok"},
            "polygon": {"ok": True, "message": "polygon ok"},
            "telegram": {"ok": True, "message": "telegram ok", "status": "SENT", "message_id": "44"},
        },
    )
    called: list[str] = []
    store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = create_operator_app(
        store,
        controller=_StubController(),
        app_builder=lambda: SimpleNamespace(
            send_telegram_test_message=lambda source: called.append(source),
            state_store=store,
        ),
        operator_settings_builder=lambda: operator_config.build_operator_settings_view(
            SimpleNamespace(
                paper_trading_mode=True,
                database_url="sqlite://",
                polygon_api_key="polygon-key",
                telegram_enabled=True,
                telegram_bot_token="token",
                telegram_chat_id="chat",
                run_interval_seconds=900,
                auto_start_runtime=False,
                delayed_data_wording_mode="standard",
                operator_state_db_path=str(tmp_path / "ops.db"),
            )
        ),
        enforce_setup=True,
    )
    client = TestClient(app)

    page = client.get("/settings")
    assert page.status_code == 200
    assert "Send Telegram Test Message" in page.text
    assert "workflow-controlled" in page.text

    response = client.post("/control/send-telegram-test", follow_redirects=False)
    assert response.status_code == 303
    assert called == ["settings-ui"]


def test_click_only_runtime_skips_setup_when_effective_runtime_is_already_valid(monkeypatch, tmp_path):
    _configure_operator_paths(monkeypatch, tmp_path)
    current_settings = SimpleNamespace(
        paper_trading_mode=True,
        database_url="sqlite://",
        polygon_api_key="polygon-key",
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        run_interval_seconds=900,
        auto_start_runtime=False,
        delayed_data_wording_mode="standard",
        operator_state_db_path=str(tmp_path / "ops.db"),
    )
    monkeypatch.setattr(
        "doctrine_engine.product.web.validate_operator_settings",
        lambda payload, send_telegram_test, telegram_label: operator_config.OperatorSettingsValidation(
            ok=True,
            details={
                "database": {"ok": True, "message": "db ok"},
                "ops_store": {"ok": True, "message": "ops ok"},
                "polygon": {"ok": True, "message": "polygon ok"},
                "telegram": {
                    "ok": True,
                    "message": "telegram configured",
                    "status": "CONFIGURED",
                    "message_id": None,
                },
            },
        ),
    )

    store = OperationalStateStore(str(tmp_path / "ops.db"))
    app = create_operator_app(
        store,
        controller=_StubController(),
        app_builder=lambda: SimpleNamespace(state_store=store, send_telegram_test_message=lambda source: None),
        operator_settings_builder=lambda: operator_config.build_operator_settings_view(current_settings),
        enforce_setup=True,
    )
    client = TestClient(app)

    bootstrap = operator_config.bootstrap_operator_settings_from_runtime(current_settings)
    assert bootstrap["settings"]["database_url"] == "sqlite://"

    overview = client.get("/", follow_redirects=False)
    settings_page = client.get("/settings", follow_redirects=False)

    assert overview.status_code == 200
    assert settings_page.status_code == 200
    assert "Overview" in overview.text
    assert 'action="/setup/save"' not in overview.text
