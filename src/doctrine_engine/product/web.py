from __future__ import annotations

from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product.state import OperationalStateStore


def create_operator_app(state_store: OperationalStateStore) -> FastAPI:
    app = FastAPI(title="Doctrine Operator")

    @app.get("/health")
    def health():
        return JSONResponse(state_store.health_snapshot())

    @app.get("/", response_class=HTMLResponse)
    def index():
        latest_run = state_store.latest_run()
        recent_runs = state_store.recent_runs(limit=10)
        latest_symbols = state_store.latest_run_symbols()
        generated_alerts = state_store.recent_alerts(limit=10, suppressed=False)
        suppressed_alerts = state_store.recent_alerts(limit=10, suppressed=True)
        recent_errors = state_store.recent_errors(limit=10)
        health_snapshot = state_store.health_snapshot()
        html = [
            "<html><head><title>Doctrine Operator</title>",
            "<style>body{font-family:Arial,sans-serif;margin:24px;}table{border-collapse:collapse;width:100%;margin-bottom:24px;}th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;}pre{white-space:pre-wrap;background:#f7f7f7;padding:12px;}h1,h2{margin-top:24px;}</style>",
            "</head><body>",
            "<h1>Doctrine Operator</h1>",
            f"<p>Last successful run: {escape(str(health_snapshot.get('last_successful_run_time')))}</p>",
            "<h2>Latest Run</h2>",
            _table([latest_run] if latest_run else [], columns=[
                "run_id", "run_status", "started_at", "finished_at", "total_symbols",
                "succeeded_symbols", "skipped_symbols", "failed_symbols",
                "sendable_alerts", "rendered_alerts", "telegram_sent", "telegram_failed",
            ]),
            "<h2>Recent Runs</h2>",
            _table(recent_runs, columns=[
                "run_id", "run_status", "finished_at", "total_symbols",
                "failed_symbols", "sendable_alerts", "telegram_sent", "telegram_failed",
            ]),
            "<h2>Latest Run Symbols</h2>",
            _table(latest_symbols, columns=[
                "ticker", "status", "stage_reached", "signal", "ranking_tier", "alert_state", "error_message",
            ]),
            "<h2>Generated Alerts</h2>",
            _alert_table(generated_alerts),
            "<h2>Suppressed Alerts</h2>",
            _alert_table(suppressed_alerts),
            "<h2>Recent Errors</h2>",
            _table(recent_errors, columns=["created_at", "ticker", "stage", "error_message"]),
            "</body></html>",
        ]
        return HTMLResponse("".join(html))

    return app


def _table(rows: list[dict], *, columns: list[str]) -> str:
    if not rows:
        return "<p>No data.</p>"
    parts = ["<table><thead><tr>"]
    parts.extend(f"<th>{escape(column)}</th>" for column in columns)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        parts.extend(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _alert_table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No alerts.</p>"
    parts = [
        "<table><thead><tr>",
        "<th>created_at</th><th>ticker</th><th>alert_state</th><th>setup_state</th><th>entry_type</th><th>telegram_status</th><th>telegram_error</th><th>preview</th>",
        "</tr></thead><tbody>",
    ]
    for row in rows:
        parts.append("<tr>")
        parts.append(f"<td>{escape(str(row.get('created_at', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('ticker', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('alert_state', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('setup_state', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('entry_type', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('telegram_status', '')))}</td>")
        parts.append(f"<td>{escape(str(row.get('telegram_error', '')))}</td>")
        parts.append(f"<td><pre>{escape(str(row.get('rendered_text', '') or ''))}</pre></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


app = create_operator_app(OperationalStateStore(get_settings().operator_state_db_path))


__all__ = ["app", "create_operator_app"]
