# Structure Doctrine Engine

Local operator product for manual paper trading of delayed-data U.S. long setups.

## Operator mode

- manual paper trading only
- no broker integration
- Telegram is the primary alert surface
- the local web console is the review and control surface
- the Windows launcher is the normal startup path

## One-click startup

Normal use does not require Terminal, PowerShell, venv activation, or direct CLI commands.

1. Open [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs).
2. In the launcher, click:
   - `Start System`
   - `Open Dashboard`
   - `Run Once Now`
   - `Restart System`
   - `Stop System`
3. Use the dashboard pages for runs, symbols, alerts, trades, errors, and settings.

The launcher auto-bootstrap path reuses the current machine runtime configuration when it is already valid. Normal operation does not require editing `.env`.

## Operator surfaces

### Telegram

Trading alerts are still controlled by doctrine + alert workflow rules.

Telegram is used for:
- sendable doctrine alerts
- labeled operator test messages from the Settings page

Suppressed, duplicate-blocked, cooldown-blocked, and non-sendable outcomes remain visible in the dashboard even when Telegram does not send anything.

### Dashboard

The FastAPI operator console provides:
- overview and health
- runs and run detail
- symbols and symbol detail
- alerts
- trades
- errors
- settings and Telegram test send

The dashboard shows:
- latest run result
- engine/web/run-once state
- full trade details for alert rows
- suppressed and sendable outcomes
- Telegram status and error
- tracked open trades and closed outcomes
- latest `known_at` freshness

## Runtime defaults

The active runtime defaults are owned by `DoctrineProductApp.build_runner_config()`:

- `timeframes.micro = "5M"`
- `require_micro_confirmation = False`

## Persistence model

The product uses two persistence layers.

### PostgreSQL doctrine data

Used for:
- market data
- features
- signals
- trade plans
- outcomes / ML labels

Active lifecycle contract:
- every qualifying `LONG` setup with a successful trade plan is persisted
- this is independent of Telegram sendability
- suppressed-but-qualified setups are still recorded for training
- non-fatal trade-plan skips do not become tracked trades because no valid plan exists

### SQLite operator data

Stored in the local ops store configured by `SDE_OPERATOR_STATE_DB_PATH`.

Used for:
- runs
- symbol outcomes
- alert history
- operator events
- Telegram transport results
- recent errors
- launcher/runtime state visibility

## ML / open-trade lifecycle

The active runtime now records doctrine-qualified setups to PostgreSQL and creates tracked outcomes.

For each qualifying setup:
- `signals` row is created
- `trade_plans` row is created
- `outcomes` row is created with `evaluation_status = PENDING`

Outcome tracking runs automatically during normal product execution and updates:
- `success_label`
- `tp2_label`
- `invalidated_first`
- `bars_tracked`
- `bars_to_tp1`
- `mfe_pct`
- `mae_pct`
- `first_barrier`

Telegram `SENT` vs `NOT_SENT` does not control ML/open-trade logging.

## Delayed-data policy

Polygon data is delayed by 15 minutes.

Operator meaning:
- `signal_timestamp` is the market event timestamp
- `known_at` is the earliest delayed-data timestamp at which the system could know the setup
- the system is an operator workflow tool, not a live execution engine

## Developer commands

These exist for development and diagnostics, not for normal operator use:

```powershell
doctrine once
doctrine loop
doctrine web
doctrine launcher
```

## Current closure docs

Operator and release truth is documented in:

- [D:\Doctrine\structure-doctrine-engine\docs\manual_trading_sop.md](D:/Doctrine/structure-doctrine-engine/docs/manual_trading_sop.md)
- [D:\Doctrine\structure-doctrine-engine\docs\operator_start_run_checklist.md](D:/Doctrine/structure-doctrine-engine/docs/operator_start_run_checklist.md)
- [D:\Doctrine\structure-doctrine-engine\docs\release_handoff.md](D:/Doctrine/structure-doctrine-engine/docs/release_handoff.md)
- [D:\Doctrine\structure-doctrine-engine\docs\runtime_validation_pack.md](D:/Doctrine/structure-doctrine-engine/docs/runtime_validation_pack.md)
- [D:\Doctrine\structure-doctrine-engine\docs\project_closure_matrix_final.md](D:/Doctrine/structure-doctrine-engine/docs/project_closure_matrix_final.md)
