# Operator Start / Run Checklist

## Start once

```powershell
doctrine once
```

## Start continuous mode

```powershell
doctrine loop
```

Optional interval override:

```powershell
doctrine loop --interval-seconds 900
```

## Open the web console

```powershell
doctrine web
```

Default local URL:
- `http://127.0.0.1:8000/`

## Check the latest run

1. Open the overview page.
2. Verify:
   - latest run status
   - total symbols
   - failed symbols
   - sendable alerts
   - Telegram sent / failed

## Read Telegram alert states

- `NEW`: fresh operator alert
- `UPGRADED`: materially improved existing alert
- `SUPPRESSED`: not actionable
- `DUPLICATE_BLOCKED`: duplicate of an already-seen alert
- `COOLDOWN_BLOCKED`: same alert family inside cooldown

## Read micro-state

- `NOT_REQUESTED`: 5M was not part of this run path
- `REQUESTED_UNAVAILABLE`: 5M was requested but not available
- `AVAILABLE_NOT_USED`: 5M existed but did not gate confirmation
- `AVAILABLE_USED`: 5M existed and gated confirmation

## When to ignore a signal

- `signal = NONE`
- alert state is suppressed / duplicate / cooldown blocked
- event risk is blocked
- alert is materially stale relative to `known_at`

## When a signal is potentially actionable

- `signal = LONG`
- alert workflow says sendable
- event risk is clear
- entry / invalidation / TP fields are present and readable
- delayed-data context is acceptable for manual review

## Where to check failures

- Web overview: latest run + recent errors
- Web alert history: Telegram status and transport errors
- Local SQLite ops state: `.doctrine/operations.db`
