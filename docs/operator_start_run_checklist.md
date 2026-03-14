# Operator Start / Run Checklist

## Open the app

1. Double-click [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs).
2. Wait for the launcher window to appear.

## Auto-bootstrap behavior

On this machine, the launcher reuses the current valid runtime configuration automatically.

You only see the setup screen if the existing machine configuration is missing or invalid.

## Start the system

1. In the launcher, click `Start System`.
2. Confirm:
   - `Engine State = RUNNING`
   - `Web State = RUNNING`

## Open the dashboard

1. In the launcher, click `Open Dashboard`.
2. The browser opens the local operator console automatically.

## If setup is required

The dashboard opens the `Setup` page only when configuration is incomplete.

The setup flow validates:
- database connectivity
- ops-store path
- Polygon credential presence
- Telegram connectivity if Telegram is enabled

## Run once now

Use either:
- launcher `Run Once Now`
- dashboard `Run Once Now`

Then confirm on the dashboard:
- latest run status
- processed / skipped / failed counts
- alerts and suppressed alerts
- tracked trades
- recent errors

## Daily operator checks

1. Open the launcher.
2. Confirm engine and web state.
3. Open the dashboard.
4. Review:
   - latest run
   - generated and suppressed alerts
   - tracked trades
   - Telegram status
   - latest `known_at`
   - recent errors

## Telegram test

From `Settings`:
1. Click `Send Telegram Test Message`.
2. Confirm a clearly labeled test message arrives.
3. Confirm the dashboard shows the transport result.

## Stop or restart

Use the launcher buttons:
- `Stop System`
- `Restart System`

The dashboard remains available even when the engine loop is stopped.
