from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from doctrine_engine.control_plane import doctrine_reviews
from doctrine_engine.control_plane.task_queue import TaskQueue
from doctrine_engine.product.state import OperationalStateStore


def _create_market_data_db(path: Path, *, latest_bar_known_at: datetime, latest_snapshot_at: datetime) -> str:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE bars (known_at TEXT, bar_timestamp TEXT)")
        connection.execute("CREATE TABLE universe_snapshots (snapshot_timestamp TEXT)")
        connection.execute(
            "INSERT INTO bars (known_at, bar_timestamp) VALUES (?, ?)",
            (latest_bar_known_at.isoformat(), latest_bar_known_at.isoformat()),
        )
        connection.execute(
            "INSERT INTO universe_snapshots (snapshot_timestamp) VALUES (?)",
            (latest_snapshot_at.isoformat(),),
        )
        connection.commit()
    finally:
        connection.close()
    return f"sqlite:///{path}"


def test_data_freshness_review_emits_ops_task_when_stale(tmp_path: Path, monkeypatch) -> None:
    stale_time = datetime.now(timezone.utc) - timedelta(days=5)
    db_url = _create_market_data_db(
        tmp_path / "doctrine.db",
        latest_bar_known_at=stale_time,
        latest_snapshot_at=stale_time,
    )
    ops_db = tmp_path / "ops.db"
    OperationalStateStore(str(ops_db))
    monkeypatch.setattr(
        doctrine_reviews,
        "get_settings",
        lambda: SimpleNamespace(database_url=db_url, operator_state_db_path=str(ops_db)),
    )
    task_dir = tmp_path / "tasks"
    monkeypatch.setattr(doctrine_reviews, "TaskQueue", lambda: TaskQueue(task_dir))

    result = doctrine_reviews.run_data_freshness_review()
    doctrine_reviews.emit_review_task(result)

    assert result.healthy is False
    payload = TaskQueue(task_dir).load()
    assert payload["proposed"][0].id == doctrine_reviews.DATA_FRESHNESS_TASK_ID
    assert payload["proposed"][0].affected_layer == "data-universe"


def test_pipeline_integrity_review_is_healthy_for_recent_successful_run(tmp_path: Path, monkeypatch) -> None:
    market_db_url = _create_market_data_db(
        tmp_path / "doctrine.db",
        latest_bar_known_at=datetime.now(timezone.utc),
        latest_snapshot_at=datetime.now(timezone.utc),
    )
    ops_db = tmp_path / "ops.db"
    store = OperationalStateStore(str(ops_db))
    connection = sqlite3.connect(ops_db)
    try:
        finished_at = datetime.now(timezone.utc).isoformat()
        started_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        connection.execute(
            """
            INSERT INTO runs (
                run_id, started_at, finished_at, run_status, total_symbols, succeeded_symbols, skipped_symbols,
                failed_symbols, generated_signals, generated_trade_plans, ranked_symbols, sendable_alerts,
                rendered_alerts, telegram_sent, telegram_failed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1",
                started_at,
                finished_at,
                "SUCCESS",
                10,
                10,
                0,
                0,
                2,
                2,
                2,
                1,
                1,
                1,
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        doctrine_reviews,
        "get_settings",
        lambda: SimpleNamespace(database_url=market_db_url, operator_state_db_path=store.path),
    )

    result = doctrine_reviews.run_pipeline_integrity_review()

    assert result.healthy is True
    assert "Latest run: status=SUCCESS" in "\n".join(result.details)
