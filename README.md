# Structure Doctrine Signal Engine

A production-grade long-only structural signal platform for U.S. stocks using delayed Polygon data.

## Scope

- U.S. stocks only
- Price between $5 and $50
- LONG signals only
- Delayed data only
- Telegram alerts for high-quality setups
- No shorting
- No broker execution in v1

## Core design

The system is built in layers:

1. Universe and data layer
2. Structural doctrine engine
3. Trade plan engine
4. Ranking and learning engine
5. Notification and reporting layer

## Primary objective

Find high-quality long opportunities based on multi-timeframe structural logic, then rank and alert only the best setups.

## Timeframes

- HTF = 4H
- MTF = 1H
- LTF = 15M
- Optional micro confirmation = 5M

## Signal outputs

The signal engine returns only:
- `LONG`
- `NONE`

## Trade plan outputs

For valid `LONG` signals, the trade plan engine returns:
- entry zone
- confirmation level
- invalidation level
- TP1
- TP2
- trail mode

## Delayed data policy

Polygon data is delayed by 15 minutes.

This means:
- no live-bar assumptions
- no same-bar fantasy execution
- all signals and plans must reflect delayed awareness honestly

## Telegram policy

Only high-grade signals should be sent:
- `A+`
- `A`

Lower-grade signals are logged but not sent.

## ML policy

ML is used only to rank valid doctrine setups.
ML must not replace the doctrine engine.

## Phase 1 Setup

1. Install Python dependencies:

```powershell
pip install -e .
```

2. Create the local PostgreSQL database:

```powershell
createdb doctrine
```

If `createdb` is not available, use `psql`:

```powershell
psql -U postgres -c "CREATE DATABASE doctrine;"
```

3. Enable TimescaleDB if the extension package is installed on your PostgreSQL server:

```powershell
psql -U postgres -d doctrine -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

4. Copy `.env.example` to `.env` and adjust credentials if needed.

5. Run the phase 1 migration:

```powershell
alembic upgrade head
```

## Migration Verification

Run this exact verification cycle locally:

```powershell
alembic upgrade head
psql -U postgres -d doctrine -c "\dt"
psql -U postgres -d doctrine -c "\di"
alembic downgrade base
alembic upgrade head
```

## Expected Phase 1 Tables

- `symbols`
- `universe_snapshots`
- `universe_snapshot_memberships`
- `bars`
- `features`
- `signals`
- `trade_plans`
- `outcomes`
- `model_runs`

## Timescale Notes

- The migration checks whether the TimescaleDB extension is available on the server.
- If TimescaleDB is available, the migration creates the extension if needed and converts `bars` into a hypertable.
- If TimescaleDB is not installed, the migration still succeeds and leaves `bars` as a normal PostgreSQL table.
- The `bars.known_at`, `features.known_at`, `signals.known_at`, and `trade_plans.known_at` columns preserve delayed-data auditability; no live-bar assumptions should be layered on top of this schema.

## Product Commands

After configuring `.env`, install the package and use the console entrypoint:

```powershell
pip install -e .
```

Single run:

```powershell
doctrine once
```

Continuous interval runner:

```powershell
doctrine loop
```

Local operator UI:

```powershell
doctrine web
```

The runner uses real provider credentials from `.env`, stores operational state in the local SQLite file configured by `SDE_OPERATOR_STATE_DB_PATH`, and the operator UI reads from that state store.

## Initial build order

1. DB schema and migrations
2. Polygon ingestion and universe filtering
3. Structural event engine
4. Zone and pattern engines
5. Regime and event-risk engines
6. Signal engine
7. Trade-plan engine
8. Telegram notifier and chart snapshots
9. Outcome tracker and labels
10. ML ranking engine
11. Monitoring, tests, and docs
