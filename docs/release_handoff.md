# Release Handoff

## Canonical branch

- Canonical local branch: `main`
- Current remote: `origin = https://github.com/alnahdi1988/lana.git`
- Current push command:

```powershell
git -C D:\Doctrine\structure-doctrine-engine push -u origin main
```

## Runtime defaults

- `DoctrineProductApp.build_runner_config()` is the owner of runtime micro defaults.
- Frozen operator baseline defaults:
  - `timeframes.micro = "5M"`
  - `require_micro_confirmation = False`
- Operator mode:
  - delayed-data operator workflow
  - Telegram primary surface
  - local web console secondary surface
  - local SQLite ops state

## Delayed-data policy

- Signals are delayed-data operator alerts, not live execution.
- `signal_timestamp` is the triggering market event time.
- `known_at` is the earliest time the full delayed input set was actually knowable.
- Telegram wording must preserve:

```text
Data: Polygon delayed 15m. Operator workflow alert only, not live execution.
```

## Micro-state semantics

- `NOT_REQUESTED`
- `REQUESTED_UNAVAILABLE`
- `AVAILABLE_NOT_USED`
- `AVAILABLE_USED`

Authoritative derivation point:
- `SignalEngine.evaluate`

Downstream propagation:
- `SignalEngineResult.extensible_context`
- `AlertDecisionPayload`
- Telegram rendered text
- SQLite ops state
- operator web UI

## Provider assumptions

- Market data: Polygon
- Event/news/calendar input: Polygon-backed product loaders
- Halt provider mode is configuration-driven
- Doctrine core market/feature persistence remains in PostgreSQL
- Operator/runtime persistence remains in local SQLite

## Release checkpoint

- Tag: `closeout-micro-state-v1`

## Remote status

- `origin/main` is configured and tracking locally.
- Release tag exists locally and remotely:
  - `closeout-micro-state-v1`
- Verification commands:

```powershell
git -C D:\Doctrine\structure-doctrine-engine remote -v
git -C D:\Doctrine\structure-doctrine-engine branch -vv
git -C D:\Doctrine\structure-doctrine-engine ls-remote --tags origin closeout-micro-state-v1
```

## Current runtime checkpoint

- Latest post-fix live run in `.doctrine/operations.db`:
  - `run_status = SUCCESS`
  - `total_symbols = 8`
  - `succeeded_symbols = 1`
  - `skipped_symbols = 7`
  - `failed_symbols = 0`
  - `generated_signals = 2`
  - `generated_trade_plans = 1`
  - `ranked_symbols = 1`

- Representative live outcomes:
  - `INTC`:
    - `status = SUCCESS`
    - `stage_reached = BUILD_ALERT_DECISION`
    - `alert_state = SUPPRESSED`
  - `IREN`:
    - `status = SKIPPED`
    - `stage_reached = BUILD_TRADE_PLAN`
    - `error_message = Invalidation anchor cannot fall inside the entry zone.`

- Latest persisted alert:
  - `ticker = INTC`
  - `alert_state = SUPPRESSED`
  - `suppression_reason = GRADE_NOT_SENDABLE`
  - `telegram_status = NOT_SENT`
  - `micro_state = AVAILABLE_NOT_USED`
  - `micro_trigger_state = LTF_BULLISH_RECLAIM`

## Push reference

```powershell
git -C D:\Doctrine\structure-doctrine-engine push origin closeout-micro-state-v1
```
