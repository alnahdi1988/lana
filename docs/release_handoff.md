# Release Handoff

## Canonical branch

- canonical branch: `main`
- tracked remote: `origin/main`
- remote URL: `https://github.com/alnahdi1988/lana.git`

## Operator startup

Normal operator entrypoint:
- [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs)

What it provides:
- launcher window
- start / stop / restart / run-once controls
- dashboard open
- no-terminal normal operation

## Runtime defaults

Owned by `DoctrineProductApp.build_runner_config()`:
- `timeframes.micro = "5M"`
- `require_micro_confirmation = False`

## Persistence split

### PostgreSQL

Doctrine and ML lifecycle persistence:
- market data
- features
- signals
- trade plans
- outcomes

### SQLite

Operator-state persistence:
- runs
- symbol_runs
- alerts
- prior alert state
- operator events
- errors

## Qualifying setup contract

Implemented doctrine tracking contract:
- `signal == LONG`
- successful trade plan build
- independent of Telegram sendability

Suppressed qualified setups are still written to PostgreSQL doctrine tables and tracked for later labels.

## Delayed-data policy

- `signal_timestamp` is the market event timestamp
- `known_at` is the delayed-data timestamp at which the setup became knowable
- the system remains an operator workflow product, not a live execution engine

## Telegram truth

- Telegram is the primary alert surface
- only workflow-sendable alerts are sent
- suppressed / duplicate / cooldown outcomes remain fully visible in the dashboard
- operator test sends are available from Settings and are persisted as `TELEGRAM_TEST_SEND`

## Current live checkpoint

Latest validated current-code run in SQLite:
- `run_id = 23d65c02-6563-46c2-b786-80f4bf373e44`
- `run_status = SUCCESS`
- `total_symbols = 8`
- `succeeded_symbols = 1`
- `skipped_symbols = 7`
- `failed_symbols = 0`
- `generated_signals = 2`
- `generated_trade_plans = 1`
- `ranked_symbols = 1`
- `sendable_alerts = 0`

Latest persisted alert row:
- `ticker = INTC`
- `signal = LONG`
- `confidence = 0.7100`
- `grade = B`
- `setup_state = BULLISH_RECLAIM`
- `entry_type = AGGRESSIVE`
- `alert_state = SUPPRESSED`
- `suppression_reason = GRADE_NOT_SENDABLE`
- `telegram_status = NOT_SENT`
- `micro_state = AVAILABLE_NOT_USED`
- `micro_trigger_state = LTF_BULLISH_RECLAIM`

Latest doctrine operator events:
- `DOCTRINE_PERSISTENCE = OK`
  - `signals=1 trade_plans=1 outcomes=1`
- `OUTCOME_TRACKER = OK`
  - `updated=0 open=2 finalized=0`

Latest PostgreSQL doctrine counts:
- `signals = 2`
- `trade_plans = 2`
- `outcomes = 2`

Latest PostgreSQL tracked trade:
- `ticker = INTC`
- `signal = LONG`
- `setup_state = BULLISH_RECLAIM`
- `entry_type = AGGRESSIVE`
- `entry_zone = 45.5550 - 47.1628`
- `invalidation = 45.1200`
- `tp1 = 47.3000`
- `tp2 = 47.3300`
- `evaluation_status = PENDING`

## Operator surfaces

The dashboard is the secondary operator surface and now exposes:
- overview
- runs and run detail
- symbols and symbol detail
- alerts
- trades
- errors
- settings

## Release truth

Current repo state is closed for manual paper-trading operation with:
- launcher-based startup
- Telegram operator delivery
- FastAPI dashboard
- SQLite operator persistence
- PostgreSQL tracked-trade / ML lifecycle persistence
