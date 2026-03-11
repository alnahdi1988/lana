from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from doctrine_engine.alerts.models import AlertDecisionResult, PriorAlertState
from doctrine_engine.product.clients import TelegramSendResult
from doctrine_engine.runner.models import RunnerResult, SymbolRunSummary


@dataclass(frozen=True, slots=True)
class StoredAlertRecord:
    run_id: str
    signal_id: str
    symbol_id: str
    ticker: str
    setup_state: str
    entry_type: str
    alert_state: str
    send: bool
    rendered_text: str | None
    telegram_status: str
    telegram_message_id: str | None
    telegram_error: str | None
    created_at: datetime


class OperationalStateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    total_symbols INTEGER NOT NULL,
                    succeeded_symbols INTEGER NOT NULL,
                    skipped_symbols INTEGER NOT NULL,
                    failed_symbols INTEGER NOT NULL,
                    generated_signals INTEGER NOT NULL,
                    generated_trade_plans INTEGER NOT NULL,
                    ranked_symbols INTEGER NOT NULL,
                    sendable_alerts INTEGER NOT NULL,
                    rendered_alerts INTEGER NOT NULL,
                    telegram_sent INTEGER NOT NULL,
                    telegram_failed INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS symbol_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    symbol_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage_reached TEXT NOT NULL,
                    signal TEXT,
                    ranking_tier TEXT,
                    alert_state TEXT,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    symbol_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    setup_state TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    alert_state TEXT NOT NULL,
                    send INTEGER NOT NULL,
                    family_key TEXT NOT NULL,
                    payload_fingerprint TEXT NOT NULL,
                    signal_timestamp TEXT NOT NULL,
                    known_at TEXT NOT NULL,
                    reason_codes_json TEXT NOT NULL,
                    rendered_text TEXT,
                    telegram_status TEXT NOT NULL,
                    telegram_message_id TEXT,
                    telegram_error TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prior_alert_states (
                    symbol_id TEXT NOT NULL,
                    setup_state TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    family_key TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    ltf_trigger_state TEXT,
                    reason_codes_json TEXT NOT NULL,
                    signal_timestamp TEXT NOT NULL,
                    known_at TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    payload_fingerprint TEXT NOT NULL,
                    PRIMARY KEY (symbol_id, setup_state, entry_type)
                );

                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    symbol_id TEXT,
                    ticker TEXT,
                    stage TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def load_prior_alert_state(self, symbol_id: uuid.UUID, setup_state: str, entry_type: str) -> PriorAlertState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM prior_alert_states
                WHERE symbol_id = ? AND setup_state = ?
                ORDER BY CASE WHEN entry_type = ? THEN 0 ELSE 1 END, sent_at DESC
                LIMIT 1
                """,
                (str(symbol_id), setup_state, entry_type),
            ).fetchone()
        if row is None:
            return None
        return PriorAlertState(
            family_key=row["family_key"],
            signal_id=uuid.UUID(row["signal_id"]),
            ticker=row["ticker"],
            signal=row["signal"],
            confidence=Decimal(row["confidence"]),
            grade=row["grade"],
            setup_state=row["setup_state"],
            entry_type=row["entry_type"],
            ltf_trigger_state=row["ltf_trigger_state"],
            reason_codes=json.loads(row["reason_codes_json"]),
            signal_timestamp=self._parse_datetime(row["signal_timestamp"]),
            known_at=self._parse_datetime(row["known_at"]),
            sent_at=self._parse_datetime(row["sent_at"]),
            payload_fingerprint=row["payload_fingerprint"],
        )

    def record_run(
        self,
        runner_result: RunnerResult,
        symbol_summaries: list[SymbolRunSummary],
        telegram_sent: int,
        telegram_failed: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id,
                    started_at,
                    finished_at,
                    run_status,
                    total_symbols,
                    succeeded_symbols,
                    skipped_symbols,
                    failed_symbols,
                    generated_signals,
                    generated_trade_plans,
                    ranked_symbols,
                    sendable_alerts,
                    rendered_alerts,
                    telegram_sent,
                    telegram_failed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(runner_result.run_id),
                    runner_result.started_at.isoformat(),
                    runner_result.finished_at.isoformat(),
                    runner_result.run_status,
                    runner_result.total_symbols,
                    runner_result.succeeded_symbols,
                    runner_result.skipped_symbols,
                    runner_result.failed_symbols,
                    runner_result.generated_signals,
                    runner_result.generated_trade_plans,
                    runner_result.ranked_symbols,
                    runner_result.sendable_alerts,
                    runner_result.rendered_alerts,
                    telegram_sent,
                    telegram_failed,
                ),
            )
            connection.execute("DELETE FROM symbol_runs WHERE run_id = ?", (str(runner_result.run_id),))
            for summary in symbol_summaries:
                connection.execute(
                    """
                    INSERT INTO symbol_runs (
                        run_id,
                        symbol_id,
                        ticker,
                        status,
                        stage_reached,
                        signal,
                        ranking_tier,
                        alert_state,
                        error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(runner_result.run_id),
                        str(summary.symbol_id),
                        summary.ticker,
                        summary.status,
                        summary.stage_reached,
                        summary.signal,
                        summary.ranking_tier,
                        summary.alert_state,
                        summary.error_message,
                    ),
                )
                if summary.error_message:
                    self._record_error_sql(
                        connection=connection,
                        run_id=str(runner_result.run_id),
                        symbol_id=str(summary.symbol_id),
                        ticker=summary.ticker,
                        stage=summary.stage_reached,
                        error_message=summary.error_message,
                    )

    def record_alert_event(
        self,
        *,
        run_id: uuid.UUID,
        signal_id: uuid.UUID,
        decision_result: AlertDecisionResult,
        rendered_text: str | None,
        transport_result: TelegramSendResult,
    ) -> None:
        payload = decision_result.payload
        created_at = transport_result.sent_at or payload.known_at
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO alerts (
                    run_id,
                    signal_id,
                    symbol_id,
                    ticker,
                    setup_state,
                    entry_type,
                    alert_state,
                    send,
                    family_key,
                    payload_fingerprint,
                    signal_timestamp,
                    known_at,
                    reason_codes_json,
                    rendered_text,
                    telegram_status,
                    telegram_message_id,
                    telegram_error,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run_id),
                    str(signal_id),
                    str(payload.symbol_id),
                    payload.ticker,
                    payload.setup_state,
                    payload.entry_type,
                    decision_result.alert_state,
                    1 if decision_result.send else 0,
                    decision_result.family_key,
                    decision_result.payload_fingerprint,
                    payload.signal_timestamp.isoformat(),
                    payload.known_at.isoformat(),
                    json.dumps(payload.reason_codes),
                    rendered_text,
                    transport_result.status,
                    transport_result.message_id,
                    transport_result.error_message,
                    created_at.isoformat(),
                ),
            )
            if transport_result.status == "SENT":
                connection.execute(
                    """
                    INSERT OR REPLACE INTO prior_alert_states (
                        symbol_id,
                        setup_state,
                        entry_type,
                        family_key,
                        signal_id,
                        ticker,
                        signal,
                        confidence,
                        grade,
                        ltf_trigger_state,
                        reason_codes_json,
                        signal_timestamp,
                        known_at,
                        sent_at,
                        payload_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(payload.symbol_id),
                        payload.setup_state,
                        payload.entry_type,
                        decision_result.family_key,
                        str(signal_id),
                        payload.ticker,
                        payload.signal,
                        format(payload.confidence, "f"),
                        payload.grade,
                        None,
                        json.dumps(payload.reason_codes),
                        payload.signal_timestamp.isoformat(),
                        payload.known_at.isoformat(),
                        (transport_result.sent_at or payload.known_at).isoformat(),
                        decision_result.payload_fingerprint,
                    ),
                )
            if transport_result.status == "FAILED":
                self._record_error_sql(
                    connection=connection,
                    run_id=str(run_id),
                    symbol_id=str(payload.symbol_id),
                    ticker=payload.ticker,
                    stage="TELEGRAM_SEND",
                    error_message=transport_result.error_message or "Telegram send failed.",
                )

    def record_error(
        self,
        *,
        run_id: uuid.UUID | None,
        symbol_id: uuid.UUID | None,
        ticker: str | None,
        stage: str,
        error_message: str,
    ) -> None:
        with self._connect() as connection:
            self._record_error_sql(
                connection=connection,
                run_id=str(run_id) if run_id is not None else None,
                symbol_id=str(symbol_id) if symbol_id is not None else None,
                ticker=ticker,
                stage=stage,
                error_message=error_message,
            )

    def recent_runs(self, limit: int = 10) -> list[dict]:
        return self._query_all(
            """
            SELECT *
            FROM runs
            ORDER BY finished_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def latest_run(self) -> dict | None:
        rows = self.recent_runs(limit=1)
        return rows[0] if rows else None

    def latest_run_symbols(self) -> list[dict]:
        latest = self.latest_run()
        if latest is None:
            return []
        return self._query_all(
            """
            SELECT *
            FROM symbol_runs
            WHERE run_id = ?
            ORDER BY ticker ASC
            """,
            (latest["run_id"],),
        )

    def recent_alerts(self, *, limit: int = 20, suppressed: bool | None = None) -> list[dict]:
        where = ""
        params: list[object] = []
        if suppressed is True:
            where = "WHERE send = 0"
        elif suppressed is False:
            where = "WHERE send = 1"
        params.append(limit)
        return self._query_all(
            f"""
            SELECT *
            FROM alerts
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )

    def recent_errors(self, limit: int = 20) -> list[dict]:
        return self._query_all(
            """
            SELECT *
            FROM errors
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def health_snapshot(self) -> dict:
        latest = self.latest_run()
        last_success = self._query_one(
            """
            SELECT finished_at
            FROM runs
            WHERE run_status = 'SUCCESS'
            ORDER BY finished_at DESC
            LIMIT 1
            """
        )
        return {
            "latest_run": latest,
            "last_successful_run_time": last_success["finished_at"] if last_success is not None else None,
        }

    def _record_error_sql(
        self,
        *,
        connection: sqlite3.Connection,
        run_id: str | None,
        symbol_id: str | None,
        ticker: str | None,
        stage: str,
        error_message: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO errors (
                run_id,
                symbol_id,
                ticker,
                stage,
                error_message,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                symbol_id,
                ticker,
                stage,
                error_message,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _query_all(self, sql: str, params: tuple[object, ...] = ()) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _query_one(self, sql: str, params: tuple[object, ...] = ()) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)


__all__ = [
    "OperationalStateStore",
    "StoredAlertRecord",
]
