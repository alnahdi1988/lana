from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from doctrine_engine.product.control import RuntimeController, RuntimePaths


def _runtime_paths(tmp_path: Path) -> RuntimePaths:
    runtime_dir = tmp_path / "runtime"
    return RuntimePaths(
        repo_root=tmp_path,
        runtime_dir=runtime_dir,
        launcher_pid_path=runtime_dir / "launcher.pid",
        engine_pid_path=runtime_dir / "engine.pid",
        engine_status_path=runtime_dir / "engine-status.json",
        engine_log_path=runtime_dir / "engine.log",
        web_pid_path=runtime_dir / "web.pid",
        web_status_path=runtime_dir / "web-status.json",
        web_log_path=runtime_dir / "web.log",
        run_once_status_path=runtime_dir / "run-once-status.json",
        run_once_log_path=runtime_dir / "run-once.log",
    )


def test_runtime_controller_start_system_enforces_single_instance(monkeypatch, tmp_path):
    monkeypatch.setattr("doctrine_engine.product.control.get_runtime_paths", lambda: _runtime_paths(tmp_path))
    monkeypatch.setattr(
        "doctrine_engine.product.control.get_settings",
        lambda: SimpleNamespace(
            run_interval_seconds=900,
            web_host="127.0.0.1",
            web_port=8000,
        ),
    )
    monkeypatch.setattr("doctrine_engine.product.control.setup_is_complete", lambda document: True)
    monkeypatch.setattr("doctrine_engine.product.control.load_operator_settings_document", lambda: {"settings": {}, "meta": {}})

    started: list[list[str]] = []

    class _FakeProcess:
        def __init__(self, pid: int):
            self.pid = pid

    monkeypatch.setattr(
        "doctrine_engine.product.control.subprocess.Popen",
        lambda command, **kwargs: started.append(command) or _FakeProcess(321),
    )
    controller = RuntimeController()
    controller.pythonw_exe.parent.mkdir(parents=True, exist_ok=True)
    controller.pythonw_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(controller, "_is_process_alive", lambda pid: pid == 321)

    controller.start_system()
    controller.start_system()

    assert len(started) == 2
    assert started[0][0].endswith("pythonw.exe")
    assert started[0][-1] == "worker-web"
    assert started[1][0].endswith("python.exe")
    assert started[1][-1] == "worker-engine"


def test_runtime_controller_does_not_respawn_recent_starting_worker(monkeypatch, tmp_path):
    monkeypatch.setattr("doctrine_engine.product.control.get_runtime_paths", lambda: _runtime_paths(tmp_path))
    monkeypatch.setattr(
        "doctrine_engine.product.control.get_settings",
        lambda: SimpleNamespace(
            run_interval_seconds=900,
            web_host="127.0.0.1",
            web_port=8000,
        ),
    )
    monkeypatch.setattr("doctrine_engine.product.control.setup_is_complete", lambda document: True)
    monkeypatch.setattr("doctrine_engine.product.control.load_operator_settings_document", lambda: {"settings": {}, "meta": {}})

    started: list[list[str]] = []

    class _FakeProcess:
        def __init__(self, pid: int):
            self.pid = pid

    monkeypatch.setattr(
        "doctrine_engine.product.control.subprocess.Popen",
        lambda command, **kwargs: started.append(command) or _FakeProcess(321),
    )
    controller = RuntimeController()
    controller.paths.web_status_path.parent.mkdir(parents=True, exist_ok=True)
    controller.paths.web_status_path.write_text(
        __import__("json").dumps(
            {
                "kind": "web",
                "state": "STARTING",
                "pid": 999999,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(controller, "_is_process_alive", lambda pid: False)

    controller.ensure_web_running()

    assert started == []


def test_runtime_controller_stop_system_calls_taskkill(monkeypatch, tmp_path):
    monkeypatch.setattr("doctrine_engine.product.control.get_runtime_paths", lambda: _runtime_paths(tmp_path))
    monkeypatch.setattr(
        "doctrine_engine.product.control.get_settings",
        lambda: SimpleNamespace(
            run_interval_seconds=900,
            web_host="127.0.0.1",
            web_port=8000,
        ),
    )
    monkeypatch.setattr("doctrine_engine.product.control.load_operator_settings_document", lambda: {"settings": {}, "meta": {}})
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "doctrine_engine.product.control.subprocess.run",
        lambda command, **kwargs: calls.append(command) or SimpleNamespace(returncode=0),
    )

    controller = RuntimeController()
    controller.paths.engine_pid_path.parent.mkdir(parents=True, exist_ok=True)
    controller.paths.engine_pid_path.write_text("444", encoding="utf-8")
    monkeypatch.setattr(controller, "_is_process_alive", lambda pid: pid == 444)

    controller.stop_system()

    assert calls == [["taskkill", "/PID", "444", "/T", "/F"]]


def test_runtime_controller_run_once_uses_console_python(monkeypatch, tmp_path):
    monkeypatch.setattr("doctrine_engine.product.control.get_runtime_paths", lambda: _runtime_paths(tmp_path))
    monkeypatch.setattr(
        "doctrine_engine.product.control.get_settings",
        lambda: SimpleNamespace(
            run_interval_seconds=900,
            web_host="127.0.0.1",
            web_port=8000,
        ),
    )
    monkeypatch.setattr("doctrine_engine.product.control.setup_is_complete", lambda document: True)
    monkeypatch.setattr("doctrine_engine.product.control.load_operator_settings_document", lambda: {"settings": {}, "meta": {}})

    started: list[list[str]] = []

    class _FakeProcess:
        def __init__(self, pid: int):
            self.pid = pid

    monkeypatch.setattr(
        "doctrine_engine.product.control.subprocess.Popen",
        lambda command, **kwargs: started.append(command) or _FakeProcess(999),
    )
    controller = RuntimeController()
    controller.run_once_now()

    assert len(started) == 1
    assert started[0][0].endswith("python.exe")
    assert started[0][-1] == "worker-once"
