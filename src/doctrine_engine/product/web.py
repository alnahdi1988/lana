from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product.control import RuntimeController
from doctrine_engine.product.operator_config import (
    build_operator_settings_view,
    load_operator_settings_document,
    merge_operator_settings,
    restart_required_keys,
    save_operator_settings_document,
    setup_is_complete,
    validate_operator_settings,
)
from doctrine_engine.product.state import OperationalStateStore

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_operator_app(
    state_store: OperationalStateStore,
    *,
    controller: RuntimeController | None = None,
    app_builder: Callable[[], Any] | None = None,
    operator_settings_builder: Callable[[], dict[str, Any]] | None = None,
    enforce_setup: bool = False,
) -> FastAPI:
    app = FastAPI(title="Doctrine Operator")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    controller = controller or RuntimeController()
    app_builder = app_builder or _default_app_builder
    operator_settings_builder = operator_settings_builder or (lambda: build_operator_settings_view(get_settings()))

    @app.get("/health")
    def health():
        payload = _status_payload(state_store, controller, operator_settings_builder, app_builder)
        payload["latest_run"] = payload["health"]["latest_run"]
        payload["last_successful_run_time"] = payload["health"]["last_successful_run_time"]
        return JSONResponse(payload)

    @app.get("/api/status")
    def api_status():
        return JSONResponse(_status_payload(state_store, controller, operator_settings_builder, app_builder))

    @app.get("/api/runs")
    def api_runs(limit: int = Query(default=20, ge=1, le=200)):
        return JSONResponse(
            {
                "latest_run": state_store.latest_run(),
                "recent_runs": state_store.recent_runs(limit=limit),
                "health": state_store.health_snapshot(),
            }
        )

    @app.get("/api/runs/{run_id}")
    def api_run_detail(run_id: str):
        return JSONResponse(
            {
                "run": state_store.run_by_id(run_id),
                "symbols": state_store.symbols_for_run(run_id),
                "alerts": state_store.alerts_for_run(run_id),
                "errors": state_store.errors_for_run(run_id),
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
        signal: str | None = None,
        setup_state: str | None = None,
        micro_state: str | None = None,
        alert_state: str | None = None,
        telegram_status: str | None = None,
        suppressed: bool | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ):
        product_app = app_builder()
        return JSONResponse(
            _enrich_alert_rows(
                product_app,
                state_store.recent_alerts(
                    limit=limit,
                    suppressed=suppressed,
                    ticker=ticker,
                    signal=signal,
                    setup_state=setup_state,
                    micro_state=micro_state,
                    alert_state=alert_state,
                    telegram_status=telegram_status,
                )
            )
        )

    @app.get("/api/trades")
    def api_trades(
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        outcome_status: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ):
        return JSONResponse(
            _recent_trades(
                app_builder(),
                limit=limit,
                ticker=ticker,
                signal=signal,
                setup_state=setup_state,
                outcome_status=outcome_status,
            )
        )

    @app.get("/api/errors")
    def api_errors(limit: int = Query(default=50, ge=1, le=500)):
        return JSONResponse(
            {
                "recent_errors": state_store.recent_errors(limit=limit),
                "grouped": state_store.grouped_recent_errors(limit=limit),
            }
        )

    @app.get("/api/settings")
    def api_settings():
        return JSONResponse(operator_settings_builder())

    @app.get("/")
    def overview(
        request: Request,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        alert_state: str | None = None,
        micro_state: str | None = None,
        telegram_status: str | None = None,
    ):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        product_app = app_builder()
        status_payload = _status_payload(state_store, controller, operator_settings_builder, app_builder)
        latest_run = state_store.latest_run()
        latest_symbols = _symbol_rows_with_latest_alerts(
            state_store,
            product_app,
            ticker=ticker,
            signal=signal,
            setup_state=setup_state,
            alert_state=alert_state,
            micro_state=micro_state,
            telegram_status=telegram_status,
        )
        generated_alerts = _enrich_alert_rows(
            product_app,
            state_store.recent_alerts(
                limit=20,
                suppressed=False,
                ticker=ticker,
                signal=signal,
                setup_state=setup_state,
                micro_state=micro_state,
                alert_state=alert_state,
                telegram_status=telegram_status,
            ),
        )
        suppressed_alerts = _enrich_alert_rows(
            product_app,
            state_store.recent_alerts(
                limit=20,
                suppressed=True,
                ticker=ticker,
                signal=signal,
                setup_state=setup_state,
                micro_state=micro_state,
                alert_state=alert_state,
                telegram_status=telegram_status,
            ),
        )
        return templates.TemplateResponse(
            request=request,
            name="overview.html",
            context=_base_context(
                request,
                page_title="Overview",
                status_payload=status_payload,
                filters={
                    "ticker": ticker or "",
                    "signal": signal or "",
                    "setup_state": setup_state or "",
                    "alert_state": alert_state or "",
                    "micro_state": micro_state or "",
                    "telegram_status": telegram_status or "",
                },
                latest_run=latest_run,
                recent_runs=state_store.recent_runs(limit=10),
                latest_symbols=latest_symbols,
                generated_alerts=generated_alerts,
                suppressed_alerts=suppressed_alerts,
                recent_trades=_recent_trades(product_app, limit=20, ticker=ticker, signal=signal, setup_state=setup_state),
                recent_errors=state_store.recent_errors(limit=20),
            ),
        )

    @app.get("/runs")
    def runs(request: Request):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        return templates.TemplateResponse(
            request=request,
            name="runs.html",
            context=_base_context(
                request,
                page_title="Runs",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                runs=state_store.recent_runs(limit=50),
            ),
        )

    @app.get("/runs/{run_id}")
    def run_detail(request: Request, run_id: str):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        run = state_store.run_by_id(run_id)
        if run is None:
            return RedirectResponse(url="/runs", status_code=303)
        product_app = app_builder()
        return templates.TemplateResponse(
            request=request,
            name="run_detail.html",
            context=_base_context(
                request,
                page_title=f"Run {run_id}",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                run=run,
                symbols=state_store.symbols_for_run(run_id),
                alerts=_enrich_alert_rows(product_app, state_store.alerts_for_run(run_id)),
                errors=state_store.errors_for_run(run_id),
            ),
        )

    @app.get("/symbols")
    def symbols(
        request: Request,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        micro_state: str | None = None,
        alert_state: str | None = None,
        telegram_status: str | None = None,
    ):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        product_app = app_builder()
        rows = _symbol_rows_with_latest_alerts(
            state_store,
            product_app,
            ticker=ticker,
            signal=signal,
            setup_state=setup_state,
            alert_state=alert_state,
            micro_state=micro_state,
            telegram_status=telegram_status,
        )
        return templates.TemplateResponse(
            request=request,
            name="symbols.html",
            context=_base_context(
                request,
                page_title="Symbols",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                symbols=rows,
                filters={
                    "ticker": ticker or "",
                    "signal": signal or "",
                    "setup_state": setup_state or "",
                    "micro_state": micro_state or "",
                    "alert_state": alert_state or "",
                    "telegram_status": telegram_status or "",
                },
            ),
        )

    @app.get("/symbols/{ticker}")
    def symbol_detail(request: Request, ticker: str):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        product_app = app_builder()
        alerts = _enrich_alert_rows(product_app, state_store.recent_alerts_for_ticker(ticker, limit=20))
        if not alerts:
            return RedirectResponse(url="/symbols", status_code=303)
        symbol_rows = _symbol_rows_with_latest_alerts(
            state_store,
            product_app,
            ticker=ticker,
            signal=None,
            setup_state=None,
            alert_state=None,
            micro_state=None,
            telegram_status=None,
        )
        errors = [row for row in state_store.recent_errors(limit=100) if row.get("ticker") == ticker]
        return templates.TemplateResponse(
            request=request,
            name="symbol_detail.html",
            context=_base_context(
                request,
                page_title=f"Symbol {ticker}",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                ticker=ticker,
                alerts=alerts,
                symbol_rows=symbol_rows,
                errors=errors,
                trades=_recent_trades(product_app, limit=50, ticker=ticker),
            ),
        )

    @app.get("/alerts")
    def alerts(
        request: Request,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        alert_state: str | None = None,
        micro_state: str | None = None,
        telegram_status: str | None = None,
    ):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        product_app = app_builder()
        rows = _enrich_alert_rows(
            product_app,
            state_store.recent_alerts(
                limit=100,
                ticker=ticker,
                signal=signal,
                setup_state=setup_state,
                micro_state=micro_state,
                alert_state=alert_state,
                telegram_status=telegram_status,
            ),
        )
        return templates.TemplateResponse(
            request=request,
            name="alerts.html",
            context=_base_context(
                request,
                page_title="Alerts",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                alerts=rows,
                filters={
                    "ticker": ticker or "",
                    "signal": signal or "",
                    "setup_state": setup_state or "",
                    "alert_state": alert_state or "",
                    "micro_state": micro_state or "",
                    "telegram_status": telegram_status or "",
                },
            ),
        )

    @app.get("/trades")
    def trades(
        request: Request,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        outcome_status: str | None = None,
    ):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        rows = _recent_trades(
            app_builder(),
            limit=100,
            ticker=ticker,
            signal=signal,
            setup_state=setup_state,
            outcome_status=outcome_status,
        )
        return templates.TemplateResponse(
            request=request,
            name="trades.html",
            context=_base_context(
                request,
                page_title="Trades",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                trades=rows,
                filters={
                    "ticker": ticker or "",
                    "signal": signal or "",
                    "setup_state": setup_state or "",
                    "outcome_status": outcome_status or "",
                },
            ),
        )

    @app.get("/errors")
    def errors(request: Request):
        redirect = _setup_redirect(request, operator_settings_builder, enforce_setup)
        if redirect is not None:
            return redirect
        grouped = state_store.grouped_recent_errors(limit=100)
        return templates.TemplateResponse(
            request=request,
            name="errors.html",
            context=_base_context(
                request,
                page_title="Errors",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                recent_errors=state_store.recent_errors(limit=100),
                errors_by_stage=grouped["by_stage"],
                errors_by_ticker=grouped["by_ticker"],
            ),
        )

    @app.get("/settings")
    def settings_page(request: Request, saved: str | None = None, restart_required: str | None = None):
        settings_view = operator_settings_builder()
        if enforce_setup and not settings_view["setup_complete"]:
            return RedirectResponse(url="/setup", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context=_base_context(
                request,
                page_title="Settings",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                operator_settings=settings_view,
                saved=saved == "1",
                restart_required_fields=[field for field in (restart_required or "").split(",") if field],
            ),
        )

    @app.get("/setup")
    def setup_page(request: Request, saved: str | None = None):
        document = load_operator_settings_document()
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context=_base_context(
                request,
                page_title="Setup",
                status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                operator_settings=document["settings"],
                validation=document["meta"]["validation"],
                setup_complete=setup_is_complete(document),
                saved=saved == "1",
            ),
        )

    @app.post("/setup/save")
    async def setup_save(request: Request):
        form = await request.form()
        payload = _settings_payload_from_form(form)
        validation = validate_operator_settings(
            payload,
            send_telegram_test=payload["telegram_enabled"],
            telegram_label="SETUP TEST | Doctrine Operator",
        )
        if not validation.ok:
            return templates.TemplateResponse(
                request=request,
                name="setup.html",
                context=_base_context(
                    request,
                    page_title="Setup",
                    status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                    operator_settings=payload,
                    validation=validation.details,
                    setup_complete=False,
                    saved=False,
                ),
                status_code=400,
            )
        save_operator_settings_document(payload, validation=validation.details)
        get_settings.cache_clear()
        controller.settings = get_settings()
        if payload["telegram_enabled"]:
            app_builder().state_store.record_operator_event(
                event_type="TELEGRAM_TEST_SEND",
                status=validation.details["telegram"]["status"],
                detail=validation.details["telegram"]["message"],
                metadata={
                    "source": "setup",
                    "message_id": validation.details["telegram"]["message_id"],
                },
            )
        return RedirectResponse(url="/settings?saved=1", status_code=303)

    @app.post("/settings/save")
    async def settings_save(request: Request):
        existing_document = load_operator_settings_document()
        existing = existing_document["settings"]
        form = await request.form()
        updated = merge_operator_settings(existing, _settings_payload_from_form(form))
        validation = validate_operator_settings(
            updated,
            send_telegram_test=False,
            telegram_label="SETTINGS TEST | Doctrine Operator",
        )
        if not validation.ok:
            return templates.TemplateResponse(
                request=request,
                name="settings.html",
                context=_base_context(
                    request,
                    page_title="Settings",
                    status_payload=_status_payload(state_store, controller, operator_settings_builder, app_builder),
                    operator_settings={**updated, "validation": validation.details},
                    saved=False,
                    restart_required_fields=[],
                    validation=validation.details,
                ),
                status_code=400,
            )
        changed = restart_required_keys(existing, updated)
        save_operator_settings_document(updated, validation=validation.details)
        get_settings.cache_clear()
        controller.settings = get_settings()
        query = ""
        if changed:
            query = "&restart_required=" + ",".join(changed)
        return RedirectResponse(url=f"/settings?saved=1{query}", status_code=303)

    @app.post("/control/start")
    def control_start():
        controller.start_system()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/control/stop")
    def control_stop():
        controller.stop_system()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/control/restart")
    def control_restart():
        controller.restart_system()
        return RedirectResponse(url="/settings", status_code=303)

    @app.post("/control/run-once")
    def control_run_once():
        controller.run_once_now()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/control/open-dashboard")
    def control_open_dashboard():
        controller.open_dashboard()
        return RedirectResponse(url="/", status_code=303)

    @app.post("/control/send-telegram-test")
    def control_send_telegram_test():
        app_builder().send_telegram_test_message(source="settings-ui")
        return RedirectResponse(url="/settings?saved=1", status_code=303)

    return app


def _default_app_builder():
    from doctrine_engine.product.service import DoctrineProductApp

    return DoctrineProductApp()


def _setup_redirect(
    request: Request,
    operator_settings_builder: Callable[[], dict[str, Any]],
    enforce_setup: bool,
) -> RedirectResponse | None:
    if not enforce_setup:
        return None
    settings_view = operator_settings_builder()
    if settings_view["setup_complete"]:
        return None
    if request.url.path.startswith("/setup"):
        return None
    return RedirectResponse(url="/setup", status_code=303)


def _status_payload(
    state_store: OperationalStateStore,
    controller: RuntimeController,
    operator_settings_builder: Callable[[], dict[str, Any]],
    app_builder: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    operator_settings = operator_settings_builder()
    health = state_store.health_snapshot()
    latest_known_at = health.get("latest_known_at")
    latest_known_age_minutes = None
    if latest_known_at:
        latest_known_age_minutes = int(
            (datetime.now(timezone.utc) - datetime.fromisoformat(str(latest_known_at))).total_seconds() // 60
        )
    latest_transport = state_store.latest_telegram_alert_event()
    latest_test = state_store.latest_operator_event("TELEGRAM_TEST_SEND")
    telegram_last = latest_transport
    if latest_test and (
        telegram_last is None
        or datetime.fromisoformat(latest_test["created_at"]) > datetime.fromisoformat(str(telegram_last["created_at"]))
    ):
        telegram_last = latest_test
    doctrine_status = {"status": "UNAVAILABLE"}
    if app_builder is not None:
        product_app = app_builder()
        snapshot = getattr(product_app, "doctrine_status_snapshot", None)
        if callable(snapshot):
            doctrine_status = snapshot()
    return {
        "runtime": controller.status_snapshot(),
        "health": health,
        "operator_settings": operator_settings,
        "ops_store_path": str(state_store.path),
        "latest_known_at": latest_known_at,
        "latest_known_age_minutes": latest_known_age_minutes,
        "latest_transport": telegram_last,
        "latest_outcome_tracker": state_store.latest_operator_event("OUTCOME_TRACKER"),
        "latest_doctrine_persistence": state_store.latest_operator_event("DOCTRINE_PERSISTENCE"),
        "doctrine": doctrine_status,
    }


def _base_context(
    request: Request,
    *,
    page_title: str,
    status_payload: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "request": request,
        "page_title": page_title,
        "status": status_payload,
        "now": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def _enrich_alert_rows(product_app: Any, alerts: list[dict]) -> list[dict]:
    enrich = getattr(product_app, "enrich_alert_rows", None)
    if callable(enrich):
        return enrich(alerts)
    return alerts


def _recent_trades(product_app: Any, **filters: Any) -> list[dict]:
    recent = getattr(product_app, "recent_trades", None)
    if callable(recent):
        return recent(**filters)
    return []


def _settings_payload_from_form(form: Any) -> dict[str, Any]:
    return {
        "paper_trading_mode": True,
        "database_url": form.get("database_url", ""),
        "polygon_api_key": form.get("polygon_api_key", ""),
        "telegram_enabled": form.get("telegram_enabled") == "on",
        "telegram_bot_token": form.get("telegram_bot_token", ""),
        "telegram_chat_id": form.get("telegram_chat_id", ""),
        "run_interval_seconds": form.get("run_interval_seconds", "900"),
        "auto_start_runtime": form.get("auto_start_runtime") == "on",
        "delayed_data_wording_mode": form.get("delayed_data_wording_mode", "standard"),
        "operator_state_db_path": form.get("operator_state_db_path", ""),
    }


def _symbol_rows_with_latest_alerts(
    state_store: OperationalStateStore,
    product_app: Any,
    *,
    ticker: str | None,
    signal: str | None,
    setup_state: str | None,
    alert_state: str | None,
    micro_state: str | None,
    telegram_status: str | None,
) -> list[dict]:
    rows = state_store.latest_run_symbols(ticker=ticker, signal=signal, alert_state=alert_state)
    enriched: list[dict] = []
    for row in rows:
        latest_alerts = _enrich_alert_rows(
            product_app,
            state_store.recent_alerts_for_ticker(str(row.get("ticker")), limit=1)
        )
        latest_alert = latest_alerts[0] if latest_alerts else None
        if setup_state and (latest_alert is None or latest_alert.get("setup_state") != setup_state):
            continue
        if micro_state and (latest_alert is None or latest_alert.get("micro_state") != micro_state):
            continue
        if telegram_status and (latest_alert is None or latest_alert.get("telegram_status") != telegram_status):
            continue
        merged = dict(row)
        merged["latest_alert"] = latest_alert
        enriched.append(merged)
    return enriched


app = create_operator_app(OperationalStateStore(get_settings().operator_state_db_path), enforce_setup=True)


__all__ = ["app", "create_operator_app"]
