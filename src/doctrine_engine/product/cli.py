from __future__ import annotations

import argparse
import logging

import uvicorn

from doctrine_engine.config.settings import get_settings
from doctrine_engine.product.service import DoctrineProductApp


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(prog="doctrine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("once")
    loop_parser = subparsers.add_parser("loop")
    loop_parser.add_argument("--interval-seconds", type=int, default=settings.run_interval_seconds)
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--host", default=settings.web_host)
    web_parser.add_argument("--port", type=int, default=settings.web_port)
    args = parser.parse_args()

    app = DoctrineProductApp(settings=settings)
    if args.command == "once":
        result = app.run_once()
        logging.getLogger(__name__).info(
            "Run complete: status=%s total_symbols=%s rendered_alerts=%s telegram_sent=%s",
            result.runner_result.run_status,
            result.runner_result.total_symbols,
            result.runner_result.rendered_alerts,
            sum(1 for item in result.transport_results if item.transport_status == "SENT"),
        )
        return
    if args.command == "loop":
        app.run_forever(interval_seconds=args.interval_seconds)
        return
    uvicorn.run(app.create_operator_app(), host=args.host, port=args.port)


app = main


__all__ = ["app", "main"]
