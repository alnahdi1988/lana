from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from doctrine_engine.product.control import RuntimeController


class DoctrineOperatorLauncher:
    def __init__(self) -> None:
        self.controller = RuntimeController()
        self.settings = self.controller.settings
        self.root = tk.Tk()
        self.root.title("Doctrine Operator")
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Doctrine Operator", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Local operator launcher. No terminal required.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 16))
        for text, command in (
            ("Start System", self._start_system),
            ("Stop System", self._stop_system),
            ("Restart System", self._restart_system),
            ("Run Once Now", self._run_once),
            ("Open Dashboard", self._open_dashboard),
            ("Open Settings", self._open_settings),
        ):
            ttk.Button(buttons, text=text, command=command).pack(fill="x", pady=4)

        self.status_text = tk.StringVar(value="Loading status...")
        ttk.Label(frame, text="Status", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            textvariable=self.status_text,
            justify="left",
            anchor="w",
            font=("Consolas", 10),
        ).pack(fill="both", expand=True)

        ttk.Button(frame, text="Close", command=self.root.destroy).pack(anchor="e", pady=(8, 0))

    def run(self) -> None:
        self.controller.ensure_web_running()
        if self.settings.auto_start_runtime and self.controller.setup_complete():
            self.controller.start_system()
        self._refresh_status()
        self.root.mainloop()

    def _start_system(self) -> None:
        self.controller.start_system()
        self._refresh_status()

    def _stop_system(self) -> None:
        self.controller.stop_system()
        self._refresh_status()

    def _restart_system(self) -> None:
        self.controller.restart_system()
        self._refresh_status()

    def _run_once(self) -> None:
        self.controller.run_once_now()
        self._refresh_status()

    def _open_dashboard(self) -> None:
        self.controller.open_dashboard()
        self._refresh_status()

    def _open_settings(self) -> None:
        self.controller.ensure_web_running()
        import webbrowser

        webbrowser.open(f"{self.controller.dashboard_url.rstrip('/')}/settings")
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self.controller.status_snapshot()
        engine = status["engine"]
        web = status["web"]
        run_once = status["run_once"]
        lines = [
            f"Setup Complete: {status['setup_complete']}",
            f"Dashboard URL : {status['dashboard_url']}",
            "",
            f"Engine State  : {engine.get('state', 'UNKNOWN')}",
            f"Engine PID    : {engine.get('pid')}",
            f"Last Run ID   : {engine.get('last_run_id')}",
            f"Last Run State: {engine.get('last_run_status')}",
            f"Last Error    : {engine.get('last_error') or '-'}",
            "",
            f"Web State     : {web.get('state', 'UNKNOWN')}",
            f"Web PID       : {web.get('pid')}",
            "",
            f"Run-Once State: {run_once.get('state', 'IDLE')}",
            f"Run-Once Last : {run_once.get('last_result_status') or '-'}",
            f"Run-Once Error: {run_once.get('last_error') or '-'}",
        ]
        self.status_text.set("\n".join(lines))
        self.root.after(3000, self._refresh_status)


def run_launcher() -> None:
    DoctrineOperatorLauncher().run()


__all__ = ["DoctrineOperatorLauncher", "run_launcher"]
