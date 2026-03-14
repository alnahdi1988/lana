# Runtime Validation Pack

## Scope

This validation pack records the closeout runtime proof for the current product layer.

The validation used:
- real `Settings()` from local `.env`
- real PostgreSQL doctrine data
- real `DbUniverseContextLoader`
- real `DbPhase2FeatureLoader`
- real `DbMarketDataLoader`
- real `DbRegimeExternalInputLoader`
- real `PolygonEventRiskInputLoader`
- real `RegimeEngine`
- real `EventRiskEngine`
- real `SignalEngine`
- real `AlertWorkflow`
- real `TelegramRenderer`
- real local SQLite ops-state persistence
- real FastAPI operator web app against that persisted state

## SOFI validation target

- `ticker = SOFI`
- `symbol_id = 319f2af7-6084-4a5b-af82-b8ca500bb891`

## Runtime config proof

```json
{
  "micro": "5M",
  "require_micro_confirmation": false
}
```

## Phase 2 proof

```json
{
  "micro_present": true,
  "micro_bar_timestamp_utc": "2026-03-11T23:55:00+00:00"
}
```

## Signal proof

```json
{
  "signal": "NONE",
  "market_regime": "RISK_OFF",
  "sector_regime": "SECTOR_WEAK",
  "event_risk_class": "NO_EVENT_RISK",
  "micro_state": "AVAILABLE_NOT_USED",
  "micro_present": true,
  "micro_trigger_state": "LTF_BULLISH_RECLAIM",
  "micro_used_for_confirmation": false
}
```

## Downstream propagation proof

For downstream payload/render/persistence/web validation, the runtime proof reused the real SOFI signal result and attached a synthetic trade-plan shell with matching symbol and timestamp fields. This was necessary because the actual live SOFI signal was `NONE`, so the real product path did not build a live trade plan for it.

The downstream propagation remained faithful to the real SOFI signal context.

Payload proof:

```json
{
  "alert_state": "SUPPRESSED",
  "market_regime": "RISK_OFF",
  "sector_regime": "SECTOR_WEAK",
  "event_risk_class": "NO_EVENT_RISK",
  "micro_state": "AVAILABLE_NOT_USED",
  "micro_present": true,
  "micro_trigger_state": "LTF_BULLISH_RECLAIM",
  "micro_used_for_confirmation": false
}
```

Rendered context line:

```text
Context: market=RISK_OFF | sector=SECTOR_WEAK | event_risk=NO_EVENT_RISK
```

Rendered micro line:

```text
Micro: state=AVAILABLE_NOT_USED | present=True | trigger=LTF_BULLISH_RECLAIM | used_for_confirmation=False
```

Persisted alert proof:

```json
{
  "ticker": "SOFI",
  "alert_state": "SUPPRESSED",
  "suppression_reason": "NOT_LONG",
  "market_regime": "RISK_OFF",
  "sector_regime": "SECTOR_WEAK",
  "event_risk_class": "NO_EVENT_RISK",
  "micro_state": "AVAILABLE_NOT_USED",
  "micro_present": 1,
  "micro_trigger_state": "LTF_BULLISH_RECLAIM",
  "micro_used_for_confirmation": 0,
  "telegram_status": "NOT_SENT",
  "telegram_error": "NOT_LONG"
}
```

Web proof:

```json
{
  "web_contains_context_and_micro": true
}
```

## Result

The closeout runtime proof confirms:
- 5M phase2 context loads for SOFI
- signal output preserves micro-state correctly
- alert payload preserves micro-state and context
- rendered operator text preserves micro-state and context
- persisted ops state preserves micro-state and context
- operator web surfaces the same persisted truth

## Latest true operator session

Real command executed:

```powershell
doctrine once
```

Observed result:

```json
{
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

Observed persisted alert:

```json
{
  "ticker": "INTC",
  "alert_state": "SUPPRESSED",
  "suppression_reason": "GRADE_NOT_SENDABLE",
  "setup_state": "RECONTAINMENT_CONFIRMED",
  "entry_type": "BASE",
  "market_regime": "BULLISH_TREND",
  "sector_regime": "SECTOR_STRONG",
  "event_risk_class": "NO_EVENT_RISK",
  "micro_state": "AVAILABLE_NOT_USED",
  "micro_present": 1,
  "micro_trigger_state": "LTF_BULLISH_RECLAIM",
  "micro_used_for_confirmation": 0,
  "telegram_status": "NOT_SENT",
  "telegram_error": "GRADE_NOT_SENDABLE"
}
```

Observed web console facts:

```json
{
  "latest_run_status": "SUCCESS",
  "web_alert_history_contains_micro_state": true,
  "web_alert_history_contains_telegram_status": true
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
