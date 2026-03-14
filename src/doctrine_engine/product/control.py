from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product.operator_config import (
    bootstrap_operator_settings_from_runtime,
    load_operator_settings_document,
    setup_is_complete,
)

WINDOWS_DETACHED_FLAGS = 0
for _name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
    WINDOWS_DETACHED_FLAGS |= int(getattr(subprocess, _name, 0))


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    repo_root: Path
    runtime_dir: Path
    engine_pid_path: Path
    engine_status_path: Path
    engine_log_path: Path
    web_pid_path: Path
    web_status_path: Path
    web_log_path: Path
    run_once_status_path: Path
    run_once_log_path: Path


def get_runtime_paths() -> RuntimePaths:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_dir = repo_root / ".doctrine" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return RuntimePaths(
        repo_root=repo_root,
        runtime_dir=runtime_dir,
        engine_pid_path=runtime_dir / "engine.pid",
        engine_status_path=runtime_dir / "engine-status.json",
        engine_log_path=runtime_dir / "engine.log",
        web_pid_path=runtime_dir / "web.pid",
        web_status_path=runtime_dir / "web-status.json",
        web_log_path=runtime_dir / "web.log",
        run_once_status_path=runtime_dir / "run-once-status.json",
        run_once_log_path=runtime_dir / "run-once.log",
    )


class RuntimeController:
    def __init__(self) -> None:
        self.paths = get_runtime_paths()
        self.settings = get_settings()
        bootstrap_operator_settings_from_runtime(self.settings)
        self.python_exe = self.paths.repo_root / ".venv" / "Scripts" / "python.exe"
        self.pythonw_exe = self.paths.repo_root / ".venv" / "Scripts" / "pythonw.exe"

    def start_system(self) -> dict[str, Any]:
        if not self.setup_complete():
            self.ensure_web_running()
            return self.status_snapshot()
        self.ensure_web_running()
        self._start_worker(
            kind="engine",
            command=[
                str(self.python_exe),
                "-c",
                "from doctrine_engine.product.control import run_engine_worker; run_engine_worker()",
            ],
            log_path=self.paths.engine_log_path,
            pid_path=self.paths.engine_pid_path,
            status_path=self.paths.engine_status_path,
            initial_status={"interval_seconds": self.settings.run_interval_seconds},
        )
        return self.status_snapshot()

    def stop_system(self) -> dict[str, Any]:
        self._stop_worker(self.paths.engine_pid_path, self.paths.engine_status_path, "engine")
        return self.status_snapshot()

    def restart_system(self) -> dict[str, Any]:
        self.stop_system()
        time.sleep(1)
        return self.start_system()

    def run_once_now(self) -> dict[str, Any]:
        if not self.setup_complete():
            self.ensure_web_running()
            return self.status_snapshot()
        current = self._coerce_status("run_once", self._read_status(self.paths.run_once_status_path), None)
        if current.get("state") == "RUNNING":
            return self.status_snapshot()
        self._write_status(
            self.paths.run_once_status_path,
            {
                "kind": "run_once",
                "state": "RUNNING",
                "pid": None,
                "last_started_at": datetime.now(timezone.utc).isoformat(),
                "last_finished_at": current.get("last_finished_at"),
                "last_result_status": current.get("last_result_status"),
                "last_error": None,
                "last_run_id": current.get("last_run_id"),
            },
        )
        self._start_worker(
            kind="run_once",
            command=[
                str(self.python_exe),
                "-c",
                "from doctrine_engine.product.control import run_once_worker; run_once_worker()",
            ],
            log_path=self.paths.run_once_log_path,
            pid_path=None,
            status_path=self.paths.run_once_status_path,
            initial_status={"kind": "run_once"},
        )
        return self.status_snapshot()

    def ensure_web_running(self) -> dict[str, Any]:
        self._start_worker(
            kind="web",
            command=[
                str(self.python_exe),
                "-c",
                "from doctrine_engine.product.control import run_web_worker; run_web_worker()",
            ],
            log_path=self.paths.web_log_path,
            pid_path=self.paths.web_pid_path,
            status_path=self.paths.web_status_path,
            initial_status={
                "host": self.settings.web_host,
                "port": self.settings.web_port,
                "url": self.dashboard_url,
            },
        )
        return self.status_snapshot()

    def stop_web(self) -> dict[str, Any]:
        self._stop_worker(self.paths.web_pid_path, self.paths.web_status_path, "web")
        return self.status_snapshot()

    def open_dashboard(self) -> dict[str, Any]:
        self.ensure_web_running()
        webbrowser.open(self.dashboard_url)
        return self.status_snapshot()

    def setup_complete(self) -> bool:
        return setup_is_complete(load_operator_settings_document())

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.settings.web_host}:{self.settings.web_port}/"

    def status_snapshot(self) -> dict[str, Any]:
        engine = self._coerce_status(
            "engine",
            self._read_status(self.paths.engine_status_path),
            self._read_pid(self.paths.engine_pid_path),
        )
        web = self._coerce_status(
            "web",
            self._read_status(self.paths.web_status_path),
            self._read_pid(self.paths.web_pid_path),
        )
        run_once = self._coerce_status(
            "run_once",
            self._read_status(self.paths.run_once_status_path),
            run_once_pid := self._read_pid(self.paths.run_once_status_path.with_suffix(".pid")),
        )
        return {
            "setup_complete": self.setup_complete(),
            "dashboard_url": self.dashboard_url,
            "engine": engine,
            "web": web,
            "run_once": run_once if run_once or run_once_pid else {"kind": "run_once", "state": "IDLE"},
        }

    def _start_worker(
        self,
        *,
        kind: str,
        command: list[str],
        log_path: Path,
        pid_path: Path | None,
        status_path: Path,
        initial_status: dict[str, Any],
    ) -> None:
        live_pid = self._read_pid(pid_path) if pid_path is not None else None
        if live_pid and self._is_process_alive(live_pid):
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            process = subprocess.Popen(
                command,
                cwd=self.paths.repo_root,
                stdout=handle,
                stderr=handle,
                creationflags=WINDOWS_DETACHED_FLAGS,
                close_fds=False,
            )
        if pid_path is not None:
            pid_path.write_text(str(process.pid), encoding="utf-8")
        self._write_status(
            status_path,
            {
                "kind": kind,
                "state": "STARTING",
                "pid": process.pid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "last_error": None,
                **initial_status,
            },
        )

    def _stop_worker(self, pid_path: Path | None, status_path: Path, kind: str) -> None:
        pid = self._read_pid(pid_path) if pid_path is not None else None
        if pid and self._is_process_alive(pid):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        if pid_path is not None and pid_path.exists():
            pid_path.unlink(missing_ok=True)
        current = self._read_status(status_path)
        self._write_status(
            status_path,
            {
                "kind": kind,
                "state": "STOPPED",
                "pid": None,
                "started_at": current.get("started_at"),
                "last_finished_at": datetime.now(timezone.utc).isoformat(),
                "last_error": current.get("last_error"),
                **{key: value for key, value in current.items() if key not in {"kind", "state", "pid", "started_at", "last_finished_at", "last_error"}},
            },
        )

    def _coerce_status(self, kind: str, data: dict[str, Any], pid: int | None) -> dict[str, Any]:
        if not data:
            return {"kind": kind, "state": "STOPPED", "pid": None}
        live_pid = pid or data.get("pid")
        state = data.get("state") or "STOPPED"
        if state in {"RUNNING", "STARTING"} and live_pid and not self._is_process_alive(int(live_pid)):
            data["state"] = "ERROR" if data.get("last_error") else "STOPPED"
            data["pid"] = None
        elif live_pid and self._is_process_alive(int(live_pid)) and kind != "run_once":
            data["state"] = "RUNNING"
            data["pid"] = int(live_pid)
        elif kind == "run_once" and state != "RUNNING":
            data.setdefault("state", "IDLE")
        return data

    def _read_pid(self, path: Path | None) -> int | None:
        if path is None or not path.exists():
            return None
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _read_status(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        return json.loads(raw)

    def _write_status(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _is_process_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if str(pid) in result.stdout:
            return True
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def run_engine_worker() -> None:
    from doctrine_engine.config.settings import get_settings
    from doctrine_engine.product.service import DoctrineProductApp

    controller = RuntimeController()
    status_path = controller.paths.engine_status_path
    pid_path = controller.paths.engine_pid_path
    settings = get_settings()
    controller._write_status(
        status_path,
        {
            "kind": "engine",
            "state": "RUNNING",
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_run_status": None,
            "last_error": None,
            "interval_seconds": settings.run_interval_seconds,
        },
    )
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    app = DoctrineProductApp(settings=settings)
    while True:
        current = controller._read_status(status_path)
        current["last_heartbeat_at"] = datetime.now(timezone.utc).isoformat()
        current["last_run_started_at"] = datetime.now(timezone.utc).isoformat()
        controller._write_status(status_path, current)
        try:
            result = app.run_once()
            current["last_run_finished_at"] = datetime.now(timezone.utc).isoformat()
            current["last_run_status"] = result.runner_result.run_status
            current["last_error"] = None
            current["state"] = "RUNNING"
            current["last_run_id"] = str(result.runner_result.run_id)
        except Exception as exc:  # pragma: no cover - exercised through worker runtime
            current["last_run_finished_at"] = datetime.now(timezone.utc).isoformat()
            current["last_run_status"] = "ERROR"
            current["last_error"] = str(exc)
            current["state"] = "ERROR"
        current["last_heartbeat_at"] = datetime.now(timezone.utc).isoformat()
        controller._write_status(status_path, current)
        time.sleep(settings.run_interval_seconds)


def run_web_worker() -> None:
    import uvicorn

    controller = RuntimeController()
    status_path = controller.paths.web_status_path
    pid_path = controller.paths.web_pid_path
    settings = get_settings()
    controller._write_status(
        status_path,
        {
            "kind": "web",
            "state": "RUNNING",
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "host": settings.web_host,
            "port": settings.web_port,
            "url": controller.dashboard_url,
            "last_error": None,
        },
    )
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    from doctrine_engine.product.service import DoctrineProductApp

    app = DoctrineProductApp(settings=settings)
    uvicorn.run(
        app.create_operator_app(),
        host=settings.web_host,
        port=settings.web_port,
        log_level=settings.log_level.lower(),
    )


def run_once_worker() -> None:
    from doctrine_engine.config.settings import get_settings
    from doctrine_engine.product.service import DoctrineProductApp

    controller = RuntimeController()
    status_path = controller.paths.run_once_status_path
    settings = get_settings()
    current = controller._read_status(status_path)
    payload = {
        "kind": "run_once",
        "state": "RUNNING",
        "pid": os.getpid(),
        "last_started_at": datetime.now(timezone.utc).isoformat(),
        "last_finished_at": current.get("last_finished_at"),
        "last_result_status": current.get("last_result_status"),
        "last_error": None,
        "last_run_id": current.get("last_run_id"),
    }
    controller._write_status(status_path, payload)
    try:
        result = DoctrineProductApp(settings=settings).run_once()
        payload["last_result_status"] = result.runner_result.run_status
        payload["last_run_id"] = str(result.runner_result.run_id)
    except Exception as exc:  # pragma: no cover - exercised through worker runtime
        payload["last_result_status"] = "ERROR"
        payload["last_error"] = str(exc)
    payload["state"] = "IDLE"
    payload["pid"] = None
    payload["last_finished_at"] = datetime.now(timezone.utc).isoformat()
    controller._write_status(status_path, payload)


__all__ = [
    "RuntimeController",
    "get_runtime_paths",
    "run_engine_worker",
    "run_once_worker",
    "run_web_worker",
]
