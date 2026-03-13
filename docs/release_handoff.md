# Release Handoff

## Canonical branch

- Canonical local branch: `main`
- Current push command once `origin` exists:

```powershell
git -C D:\Doctrine\structure-doctrine-engine push -u origin main
```

## Runtime defaults

- `DoctrineProductApp.build_runner_config()` is the owner of runtime micro defaults.
- Current defaults:
  - `timeframes.micro = "5M"`
  - `require_micro_confirmation = False`

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
