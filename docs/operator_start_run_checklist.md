# Operator Start / Run Checklist

## Open the app

1. Double-click:
   - `Doctrine Operator.vbs`
2. Wait for the launcher window to appear.

## Start the system

1. In the launcher, click `Start System`.
2. Confirm:
   - `Engine State = RUNNING`
   - `Web State = RUNNING`

## Open the dashboard

1. In the launcher, click `Open Dashboard`.
2. The browser opens the local operator console automatically.

## First-run setup

If setup is required, the dashboard opens the `Setup` page.

Fill in:
- database URL
- Polygon API key
- Telegram enabled on/off
- Telegram bot token
- Telegram chat ID
- run interval

Then click `Validate and Save`.

Success means:
- database connectivity validated
- ops-store path validated
- Telegram test message sent if Telegram is enabled

## Run once now

Use either:
- launcher `Run Once Now`
- dashboard `Run Once Now`

Then confirm on the dashboard:
- latest run status
- processed / skipped / failed counts
- alerts and suppressed alerts
- recent errors

## Daily operator checks

1. Open the launcher.
2. Confirm engine and web are running.
3. Open the dashboard.
4. Review:
   - latest run
   - generated alerts
   - suppressed alerts
   - Telegram status
   - latest `known_at`
   - recent errors

## Telegram test

From the dashboard `Settings` page:
1. Click `Send Telegram Test Message`.
2. Confirm a clearly labeled test message arrives.
3. Confirm the dashboard shows the latest transport result.

## Stop or restart

Use the launcher buttons:
- `Stop System`
- `Restart System`

The dashboard remains available even when the engine loop is stopped.
