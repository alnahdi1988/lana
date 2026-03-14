from __future__ import annotations

from html import escape

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product.state import OperationalStateStore


def create_operator_app(state_store: OperationalStateStore) -> FastAPI:
    app = FastAPI(title="Doctrine Operator")

    @app.get("/health")
    def health():
        return JSONResponse(state_store.health_snapshot())

    @app.get("/api/runs")
    def api_runs(limit: int = Query(default=20, ge=1, le=200)):
        return JSONResponse(
            {
                "latest_run": state_store.latest_run(),
                "recent_runs": state_store.recent_runs(limit=limit),
                "health": state_store.health_snapshot(),
            }
        )

    @app.get("/api/symbols")
    def api_symbols(
        ticker: str | None = None,
        signal: str | None = None,
        alert_state: str | None = None,
    ):
        return JSONResponse(
            state_store.latest_run_symbols(
                ticker=ticker,
                signal=signal,
                alert_state=alert_state,
            )
        )

    @app.get("/api/alerts")
    def api_alerts(
        ticker: str | None = None,
        setup_state: str | None = None,
        micro_state: str | None = None,
        alert_state: str | None = None,
        telegram_status: str | None = None,
        suppressed: bool | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ):
        return JSONResponse(
            state_store.recent_alerts(
                limit=limit,
                suppressed=suppressed,
                ticker=ticker,
                setup_state=setup_state,
                micro_state=micro_state,
                alert_state=alert_state,
                telegram_status=telegram_status,
            )
        )

    @app.get("/api/errors")
    def api_errors(limit: int = Query(default=50, ge=1, le=500)):
        return JSONResponse(state_store.recent_errors(limit=limit))

    @app.get("/symbols/{ticker}", response_class=HTMLResponse)
    def symbol_detail(ticker: str):
        alerts = state_store.recent_alerts_for_ticker(ticker, limit=20)
        if not alerts:
            return HTMLResponse(f"<html><body><h1>{escape(ticker)}</h1><p>No alert history.</p></body></html>", status_code=404)
        html = [
            "<html><head><title>Doctrine Symbol Detail</title>",
            _style_block(),
            "</head><body>",
            f"<h1>{escape(ticker)}</h1>",
            "<p><a href='/'>Back to overview</a></p>",
            "<h2>Recent Alerts</h2>",
            _alert_table(alerts),
            "</body></html>",
        ]
        return HTMLResponse("".join(html))

    @app.get("/", response_class=HTMLResponse)
    def index(
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        micro_state: str | None = None,
        alert_state: str | None = None,
        telegram_status: str | None = None,
    ):
        latest_run = state_store.latest_run()
        recent_runs = state_store.recent_runs(limit=10)
        latest_symbols = state_store.latest_run_symbols(
            ticker=ticker,
            signal=signal,
            alert_state=alert_state,
        )
        generated_alerts = state_store.recent_alerts(
            limit=20,
            suppressed=False,
            ticker=ticker,
            setup_state=setup_state,
            micro_state=micro_state,
            alert_state=alert_state,
            telegram_status=telegram_status,
        )
        suppressed_alerts = state_store.recent_alerts(
            limit=20,
            suppressed=True,
            ticker=ticker,
            setup_state=setup_state,
            micro_state=micro_state,
            alert_state=alert_state,
            telegram_status=telegram_status,
        )
        recent_errors = state_store.recent_errors(limit=20)
        health_snapshot = state_store.health_snapshot()
        html = [
            "<html><head><title>Doctrine Operator</title>",
            _style_block(),
            "</head><body>",
            "<h1>Doctrine Operator</h1>",
            (
                f"<p>Last successful run: "
                f"{escape(str(health_snapshot.get('last_successful_run_time')))}</p>"
            ),
            _filter_form(
                ticker=ticker,
                signal=signal,
                setup_state=setup_state,
                micro_state=micro_state,
                alert_state=alert_state,
                telegram_status=telegram_status,
            ),
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
            _symbol_table(latest_symbols),
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


def _style_block() -> str:
    return (
        "<style>"
        "body{font-family:Arial,sans-serif;margin:24px;}"
        "table{border-collapse:collapse;width:100%;margin-bottom:24px;}"
        "th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top;}"
        "pre{white-space:pre-wrap;background:#f7f7f7;padding:12px;margin:0;}"
        "h1,h2{margin-top:24px;}"
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;background:#eee;font-size:12px;}"
        "form.filter-grid{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px;margin:16px 0 24px;}"
        "form.filter-grid input{padding:6px;}"
        "form.filter-grid button{padding:6px 12px;}"
        "</style>"
    )


def _filter_form(
    *,
    ticker: str | None,
    signal: str | None,
    setup_state: str | None,
    micro_state: str | None,
    alert_state: str | None,
    telegram_status: str | None,
) -> str:
    fields = {
        "ticker": ticker or "",
        "signal": signal or "",
        "setup_state": setup_state or "",
        "micro_state": micro_state or "",
        "alert_state": alert_state or "",
        "telegram_status": telegram_status or "",
    }
    parts = ["<form class='filter-grid' method='get'>"]
    for name, value in fields.items():
        parts.append(
            f"<label>{escape(name)}<input type='text' name='{escape(name)}' value='{escape(value)}' /></label>"
        )
    parts.append("<button type='submit'>Filter</button>")
    parts.append("<a href='/'><button type='button'>Reset</button></a>")
    parts.append("</form>")
    return "".join(parts)


def _badge(value: object) -> str:
    return f"<span class='badge'>{escape(str(value))}</span>"


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


def _symbol_table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No data.</p>"
    parts = [
        "<table><thead><tr>",
        "<th>ticker</th><th>status</th><th>stage_reached</th><th>signal</th>"
        "<th>ranking_tier</th><th>alert_state</th><th>error_message</th>",
        "</tr></thead><tbody>",
    ]
    for row in rows:
        ticker = str(row.get("ticker", "") or "")
        parts.append("<tr>")
        parts.append(f"<td><a href='/symbols/{escape(ticker)}'>{escape(ticker)}</a></td>")
        parts.append(f"<td>{_badge(row.get('status', ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('stage_reached', '') or ''))}</td>")
        parts.append(f"<td>{_badge(row.get('signal', '') or '')}</td>")
        parts.append(f"<td>{_badge(row.get('ranking_tier', '') or '')}</td>")
        parts.append(f"<td>{_badge(row.get('alert_state', '') or '')}</td>")
        parts.append(f"<td>{escape(str(row.get('error_message', '') or ''))}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _alert_table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No alerts.</p>"
    parts = [
        "<table><thead><tr>",
        "<th>Created At</th><th>Ticker</th><th>Alert State</th><th>Suppression Reason</th>"
        "<th>Setup State</th><th>Entry Type</th><th>Signal Time</th><th>Known At</th>"
        "<th>Market Regime</th><th>Sector Regime</th><th>Event Risk</th>"
        "<th>Micro State</th><th>Micro Present</th><th>Micro Trigger</th>"
        "<th>Micro Used for Confirmation</th><th>Telegram Status</th>"
        "<th>Telegram Error</th><th>Operator Summary</th><th>Rendered Preview</th>",
        "</tr></thead><tbody>",
    ]
    for row in rows:
        micro_present_raw = row.get("micro_present")
        micro_used_raw = row.get("micro_used_for_confirmation")
        ticker = str(row.get("ticker", "") or "")
        parts.append("<tr>")
        parts.append(f"<td>{escape(str(row.get('created_at', '')))}</td>")
        parts.append(f"<td><a href='/symbols/{escape(ticker)}'>{escape(ticker)}</a></td>")
        parts.append(f"<td>{_badge(row.get('alert_state', '') or '')}</td>")
        parts.append(f"<td>{escape(str(row.get('suppression_reason', '') or ''))}</td>")
        parts.append(f"<td>{_badge(row.get('setup_state', '') or '')}</td>")
        parts.append(f"<td>{_badge(row.get('entry_type', '') or '')}</td>")
        parts.append(f"<td>{escape(str(row.get('signal_timestamp', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('known_at', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('market_regime', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('sector_regime', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('event_risk_class', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(row.get('micro_state', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(bool(micro_present_raw)) if micro_present_raw is not None else '')}</td>")
        parts.append(f"<td>{escape(str(row.get('micro_trigger_state', '') or ''))}</td>")
        parts.append(f"<td>{escape(str(bool(micro_used_raw)) if micro_used_raw is not None else '')}</td>")
        parts.append(f"<td>{_badge(row.get('telegram_status', '') or '')}</td>")
        parts.append(f"<td>{escape(str(row.get('telegram_error', '') or ''))}</td>")
        parts.append(f"<td><pre>{escape(str(row.get('operator_summary', '') or ''))}</pre></td>")
        parts.append(f"<td><pre>{escape(str(row.get('rendered_text', '') or ''))}</pre></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


app = create_operator_app(OperationalStateStore(get_settings().operator_state_db_path))


__all__ = ["app", "create_operator_app"]
