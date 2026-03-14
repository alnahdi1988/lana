from __future__ import annotations

from doctrine_engine.product import launcher


def test_run_launcher_invokes_launcher_class(monkeypatch):
    called: list[str] = []
    pid_path = __import__("pathlib").Path.cwd() / "launcher-test.pid"

    class _StubLauncher:
        def run(self):
            called.append("run")

    monkeypatch.setattr(launcher, "get_runtime_paths", lambda: type("Paths", (), {"launcher_pid_path": pid_path})())
    monkeypatch.setattr(launcher, "_acquire_launcher_mutex", lambda: object())
    monkeypatch.setattr(launcher, "_release_launcher_mutex", lambda: None)
    monkeypatch.setattr(launcher, "_current_pid", lambda: 111)
    monkeypatch.setattr(launcher, "DoctrineOperatorLauncher", _StubLauncher)

    launcher.run_launcher()

    assert called == ["run"]
    pid_path.unlink(missing_ok=True)


def test_run_launcher_does_not_open_second_window_when_launcher_is_already_running(monkeypatch, tmp_path):
    called: list[str] = []
    pid_path = tmp_path / "launcher.pid"
    pid_path.write_text("123", encoding="utf-8")

    monkeypatch.setattr(launcher, "get_runtime_paths", lambda: type("Paths", (), {"launcher_pid_path": pid_path})())
    monkeypatch.setattr(launcher, "_acquire_launcher_mutex", lambda: None)

    class _StubController:
        def open_dashboard(self):
            called.append("open_dashboard")

    class _ExitCalled(Exception):
        pass

    monkeypatch.setattr(launcher, "RuntimeController", _StubController)
    monkeypatch.setattr(launcher.os, "_exit", lambda code: (_ for _ in ()).throw(_ExitCalled(code)))
    monkeypatch.setattr(
        launcher,
        "DoctrineOperatorLauncher",
        lambda: type("Launcher", (), {"run": lambda self: called.append("run")})(),
    )

    try:
        launcher.run_launcher()
    except _ExitCalled:
        pass

    assert called == ["open_dashboard"]
