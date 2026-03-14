from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product import cli


def test_cli_once_resolves_repo_local_settings_outside_repo_cwd(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class StubApp:
        def __init__(self, *, settings):
            captured["settings"] = settings

        def run_once(self):
            captured["command"] = "once"
            return SimpleNamespace(
                runner_result=SimpleNamespace(
                    run_status="SUCCESS",
                    total_symbols=1,
                    rendered_alerts=0,
                ),
                transport_results=[],
            )

        def run_forever(self, *, interval_seconds: int):
            raise AssertionError("loop path should not run in this test")

        def create_operator_app(self):
            raise AssertionError("web path should not run in this test")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SDE_OPERATOR_STATE_DB_PATH", ".doctrine/operations.db")
    monkeypatch.setattr(cli, "DoctrineProductApp", StubApp)
    monkeypatch.setattr("sys.argv", ["doctrine", "once"])
    get_settings.cache_clear()
    try:
        cli.main()
    finally:
        get_settings.cache_clear()

    expected = (Path(__file__).resolve().parents[2] / ".doctrine" / "operations.db").resolve()
    settings = captured["settings"]
    assert captured["command"] == "once"
    assert Path(settings.operator_state_db_path) == expected


def test_cli_web_resolves_repo_local_settings_outside_repo_cwd(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class StubApp:
        def __init__(self, *, settings):
            captured["settings"] = settings

        def run_once(self):
            raise AssertionError("once path should not run in this test")

        def run_forever(self, *, interval_seconds: int):
            raise AssertionError("loop path should not run in this test")

        def create_operator_app(self):
            captured["command"] = "web"
            return "stub-app"

    def fake_run(app, *, host: str, port: int):
        captured["uvicorn_app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SDE_OPERATOR_STATE_DB_PATH", ".doctrine/operations.db")
    monkeypatch.setattr(cli, "DoctrineProductApp", StubApp)
    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["doctrine", "web"])
    get_settings.cache_clear()
    try:
        cli.main()
    finally:
        get_settings.cache_clear()

    expected = (Path(__file__).resolve().parents[2] / ".doctrine" / "operations.db").resolve()
    settings = captured["settings"]
    assert captured["command"] == "web"
    assert captured["uvicorn_app"] == "stub-app"
    assert captured["host"] == settings.web_host
    assert captured["port"] == settings.web_port
    assert Path(settings.operator_state_db_path) == expected
