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
                    signal TEXT NOT NULL DEFAULT 'LONG',
                    confidence TEXT,
                    grade TEXT,
                    signal_timestamp TEXT NOT NULL,
                    known_at TEXT NOT NULL,
                    entry_zone_low TEXT,
                    entry_zone_high TEXT,
                    confirmation_level TEXT,
                    invalidation_level TEXT,
                    tp1 TEXT,
                    tp2 TEXT,
                    suppression_reason TEXT,
                    prior_signal_id TEXT,
                    prior_sent_at TEXT,
                    prior_payload_fingerprint TEXT,
                    operator_summary TEXT NOT NULL,
                    reason_codes_json TEXT NOT NULL,
                    market_regime TEXT,
                    sector_regime TEXT,
                    event_risk_class TEXT,
                    micro_state TEXT,
                    micro_present INTEGER,
                    micro_trigger_state TEXT,
                    micro_used_for_confirmation INTEGER,
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

                CREATE TABLE IF NOT EXISTS operator_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            # Migrate existing alerts tables that predate micro columns
            existing_cols = {row[1] for row in connection.execute("PRAGMA table_info(alerts)").fetchall()}
            for col_def in (
                "suppression_reason TEXT",
                "signal TEXT DEFAULT 'LONG'",
                "confidence TEXT",
                "grade TEXT",
                "entry_zone_low TEXT",
                "entry_zone_high TEXT",
                "confirmation_level TEXT",
                "invalidation_level TEXT",
                "tp1 TEXT",
                "tp2 TEXT",
                "prior_signal_id TEXT",
                "prior_sent_at TEXT",
                "prior_payload_fingerprint TEXT",
                "operator_summary TEXT",
                "market_regime TEXT",
                "sector_regime TEXT",
                "event_risk_class TEXT",
                "micro_state TEXT",
                "micro_present INTEGER",
                "micro_trigger_state TEXT",
                "micro_used_for_confirmation INTEGER",
            ):
                col_name = col_def.split()[0]
                if col_name not in existing_cols:
                    connection.execute(f"ALTER TABLE alerts ADD COLUMN {col_def}")

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
                if summary.status == "FAILED" and summary.error_message:
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
        prior_alert_state: PriorAlertState | None = None,
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
                    signal,
                    confidence,
                    grade,
                    signal_timestamp,
                    known_at,
                    entry_zone_low,
                    entry_zone_high,
                    confirmation_level,
                    invalidation_level,
                    tp1,
                    tp2,
                    suppression_reason,
                    prior_signal_id,
                    prior_sent_at,
                    prior_payload_fingerprint,
                    operator_summary,
                    reason_codes_json,
                    market_regime,
                    sector_regime,
                    event_risk_class,
                    micro_state,
                    micro_present,
                    micro_trigger_state,
                    micro_used_for_confirmation,
                    rendered_text,
                    telegram_status,
                    telegram_message_id,
                    telegram_error,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    payload.signal,
                    format(payload.confidence, "f"),
                    payload.grade,
                    payload.signal_timestamp.isoformat(),
                    payload.known_at.isoformat(),
                    format(payload.entry_zone_low, "f"),
                    format(payload.entry_zone_high, "f"),
                    format(payload.confirmation_level, "f"),
                    format(payload.invalidation_level, "f"),
                    format(payload.tp1, "f"),
                    format(payload.tp2, "f"),
                    decision_result.suppression_reason,
                    str(prior_alert_state.signal_id) if prior_alert_state is not None else None,
                    prior_alert_state.sent_at.isoformat() if prior_alert_state is not None else None,
                    prior_alert_state.payload_fingerprint if prior_alert_state is not None else None,
                    payload.operator_summary,
                    json.dumps(payload.reason_codes),
                    payload.market_regime,
                    payload.sector_regime,
                    payload.event_risk_class,
                    payload.micro_state,
                    1 if payload.micro_present else 0,
                    payload.micro_trigger_state,
                    1 if payload.micro_used_for_confirmation else 0,
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

    def run_by_id(self, run_id: uuid.UUID | str) -> dict | None:
        return self._query_one(
            """
            SELECT *
            FROM runs
            WHERE run_id = ?
            """,
            (str(run_id),),
        )

    def latest_run_symbols(
        self,
        *,
        ticker: str | None = None,
        signal: str | None = None,
        alert_state: str | None = None,
    ) -> list[dict]:
        latest = self.latest_run()
        if latest is None:
            return []
        where_parts = ["run_id = ?"]
        params: list[object] = [latest["run_id"]]
        if ticker:
            where_parts.append("ticker = ?")
            params.append(ticker)
        if signal:
            where_parts.append("signal = ?")
            params.append(signal)
        if alert_state:
            where_parts.append("alert_state = ?")
            params.append(alert_state)
        return self._query_all(
            f"""
            SELECT *
            FROM symbol_runs
            WHERE {" AND ".join(where_parts)}
            ORDER BY ticker ASC
            """,
            tuple(params),
        )

    def symbols_for_run(self, run_id: uuid.UUID | str) -> list[dict]:
        return self._query_all(
            """
            SELECT *
            FROM symbol_runs
            WHERE run_id = ?
            ORDER BY ticker ASC
            """,
            (str(run_id),),
        )

    def recent_alerts(
        self,
        *,
        limit: int = 20,
        suppressed: bool | None = None,
        ticker: str | None = None,
        signal: str | None = None,
        setup_state: str | None = None,
        micro_state: str | None = None,
        alert_state: str | None = None,
        telegram_status: str | None = None,
    ) -> list[dict]:
        where_parts: list[str] = []
        params: list[object] = []
        if suppressed is True:
            where_parts.append("send = 0")
        elif suppressed is False:
            where_parts.append("send = 1")
        if ticker:
            where_parts.append("ticker = ?")
            params.append(ticker)
        if signal:
            where_parts.append("signal = ?")
            params.append(signal)
        if setup_state:
            where_parts.append("setup_state = ?")
            params.append(setup_state)
        if micro_state:
            where_parts.append("micro_state = ?")
            params.append(micro_state)
        if alert_state:
            where_parts.append("alert_state = ?")
            params.append(alert_state)
        if telegram_status:
            where_parts.append("telegram_status = ?")
            params.append(telegram_status)
        params.append(limit)
        where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
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

    def recent_alerts_for_ticker(self, ticker: str, *, limit: int = 20) -> list[dict]:
        return self.recent_alerts(limit=limit, ticker=ticker)

    def alerts_for_run(self, run_id: uuid.UUID | str, *, limit: int = 200) -> list[dict]:
        return self._query_all(
            """
            SELECT *
            FROM alerts
            WHERE run_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(run_id), limit),
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

    def errors_for_run(self, run_id: uuid.UUID | str, *, limit: int = 200) -> list[dict]:
        return self._query_all(
            """
            SELECT *
            FROM errors
            WHERE run_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(run_id), limit),
        )

    def latest_known_at(self) -> str | None:
        row = self._query_one(
            """
            SELECT known_at
            FROM alerts
            ORDER BY known_at DESC
            LIMIT 1
            """
        )
        return row["known_at"] if row is not None else None

    def latest_telegram_alert_event(self) -> dict | None:
        return self._query_one(
            """
            SELECT ticker, alert_state, telegram_status, telegram_message_id, telegram_error, created_at
            FROM alerts
            WHERE telegram_status IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

    def record_operator_event(
        self,
        *,
        event_type: str,
        status: str,
        detail: str | None,
        metadata: dict | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO operator_events (
                    event_type,
                    status,
                    detail,
                    metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    status,
                    detail,
                    json.dumps(metadata or {}),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def recent_operator_events(
        self,
        *,
        event_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        params: list[object] = []
        where = ""
        if event_type:
            where = "WHERE event_type = ?"
            params.append(event_type)
        params.append(limit)
        rows = self._query_all(
            f"""
            SELECT *
            FROM operator_events
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        for row in rows:
            row["metadata"] = json.loads(row.pop("metadata_json"))
        return rows

    def latest_operator_event(self, event_type: str | None = None) -> dict | None:
        rows = self.recent_operator_events(event_type=event_type, limit=1)
        return rows[0] if rows else None

    def grouped_recent_errors(self, limit: int = 100) -> dict[str, dict[str, list[dict]]]:
        rows = self.recent_errors(limit=limit)
        by_stage: dict[str, list[dict]] = {}
        by_ticker: dict[str, list[dict]] = {}
        for row in rows:
            stage = str(row.get("stage") or "UNKNOWN")
            ticker = str(row.get("ticker") or "SYSTEM")
            by_stage.setdefault(stage, []).append(row)
            by_ticker.setdefault(ticker, []).append(row)
        return {"by_stage": by_stage, "by_ticker": by_ticker}

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
            "latest_known_at": self.latest_known_at(),
            "latest_telegram_alert_event": self.latest_telegram_alert_event(),
            "latest_operator_telegram_test": self.latest_operator_event("TELEGRAM_TEST_SEND"),
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
