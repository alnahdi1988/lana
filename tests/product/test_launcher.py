from __future__ import annotations

from doctrine_engine.product import launcher


def test_run_launcher_invokes_launcher_class(monkeypatch):
    called: list[str] = []

    class _StubLauncher:
        def run(self):
            called.append("run")

    monkeypatch.setattr(launcher, "DoctrineOperatorLauncher", _StubLauncher)

    launcher.run_launcher()

    assert called == ["run"]
