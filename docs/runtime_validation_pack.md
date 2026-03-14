# Runtime Validation Pack

## Scope

This validation pack records the current closure-pass runtime proof for the product layer.

Validation uses:
- real local `.env` and operator settings
- real PostgreSQL doctrine data
- real SQLite operator-state data
- real `DoctrineProductApp`
- real Telegram transport for labeled operator test send
- real launcher path
- real FastAPI operator console

## Locked runtime defaults

```json
{
  "micro": "5M",
  "require_micro_confirmation": false
}
```

## Operator-shell proof

Validated entrypoint:
- [D:\Doctrine\structure-doctrine-engine\Doctrine Operator.vbs](D:/Doctrine/structure-doctrine-engine/Doctrine%20Operator.vbs)

Validated control facts:

```json
{
  "setup_complete": true,
  "dashboard_url": "http://127.0.0.1:8000/",
  "engine_state": "STOPPED",
  "web_state": "RUNNING",
  "run_once_state": "IDLE",
  "last_run_once_status": "SUCCESS"
}
```

## Latest true operator run

Observed SQLite run row:

```json
{
  "run_id": "23d65c02-6563-46c2-b786-80f4bf373e44",
  "run_status": "SUCCESS",
  "total_symbols": 8,
  "succeeded_symbols": 1,
  "skipped_symbols": 7,
  "failed_symbols": 0,
  "generated_signals": 2,
  "generated_trade_plans": 1,
  "ranked_symbols": 1,
  "sendable_alerts": 0,
  "rendered_alerts": 0,
  "telegram_sent": 0,
  "telegram_failed": 0
}
```

Observed SQLite alert row:

```json
{
  "ticker": "INTC",
  "signal": "LONG",
  "confidence": "0.7100",
  "grade": "B",
  "setup_state": "BULLISH_RECLAIM",
  "entry_type": "AGGRESSIVE",
  "entry_zone_low": "45.5550",
  "entry_zone_high": "47.162750",
  "confirmation_level": "47.2275",
  "invalidation_level": "45.1200",
  "tp1": "47.3000",
  "tp2": "47.3300",
  "alert_state": "SUPPRESSED",
  "suppression_reason": "GRADE_NOT_SENDABLE",
  "telegram_status": "NOT_SENT",
  "micro_state": "AVAILABLE_NOT_USED",
  "micro_present": 1,
  "micro_trigger_state": "LTF_BULLISH_RECLAIM",
  "micro_used_for_confirmation": 0
}
```

Observed skipped-symbol classification:

```json
{
  "ticker": "IREN",
  "status": "SKIPPED",
  "stage_reached": "BUILD_TRADE_PLAN",
  "error_message": "Invalidation anchor cannot fall inside the entry zone."
}
```

## Doctrine lifecycle proof

Observed SQLite operator events:

```json
{
  "doctrine_persistence": {
    "status": "OK",
    "detail": "signals=1 trade_plans=1 outcomes=1"
  },
  "outcome_tracker": {
    "status": "OK",
    "detail": "updated=0 open=2 finalized=0",
    "tracking_timeframe": "15M",
    "time_barrier_bars": 20
  }
}
```

Observed PostgreSQL doctrine rows:

```json
{
  "counts": {
    "signals": 2,
    "trade_plans": 2,
    "outcomes": 2
  },
  "latest_signal": {
    "id": "72648634-3672-414d-a587-c8d6bdfaabc6",
    "signal": "LONG",
    "confidence": "0.7100",
    "grade": "B",
    "setup_state": "BULLISH_RECLAIM",
    "alert_state": "SUPPRESSED",
    "suppression_reason": "GRADE_NOT_SENDABLE"
  },
  "latest_trade_plan": {
    "signal_id": "72648634-3672-414d-a587-c8d6bdfaabc6",
    "entry_type": "AGGRESSIVE",
    "entry_zone_low": "45.5550",
    "entry_zone_high": "47.1628",
    "invalidation_level": "45.1200",
    "tp1": "47.3000",
    "tp2": "47.3300"
  },
  "latest_outcome": {
    "signal_id": "72648634-3672-414d-a587-c8d6bdfaabc6",
    "evaluation_status": "PENDING",
    "bars_tracked": 0
  }
}
```

## Telegram proof

Observed real operator test send:

```json
{
  "event_type": "TELEGRAM_TEST_SEND",
  "status": "SENT",
  "source": "closure-pass",
  "message_id": "223"
}
```

## Web proof

Real browser validation against [http://127.0.0.1:8000/](http://127.0.0.1:8000/) confirmed:
- dashboard loads without terminal usage
- `Trades` page exists
- latest run shows `SUCCESS`
- latest symbol row shows `INTC` with `Outcome = PENDING`
- suppressed alert row shows full trade details
- tracked trades table shows PostgreSQL outcome status and alert-layer context together

## Result

The current closure pass proves:
- no-terminal operator startup path works
- SQLite operator truth is current and complete for alert/runs/errors/transport
- PostgreSQL doctrine lifecycle persistence is active for qualifying setups
- suppressed qualified setups are tracked for ML/outcome labels
- outcome tracking runs automatically during product execution
- Telegram operator test send works without affecting trading workflow
- the dashboard exposes joined alert-layer and trade-lifecycle truth
