# extensible_context Propagation Audit

**Date:** 2026-03-14
**Source:** `SignalEngine.evaluate` → `extensible_context` dict

## Fields and Their Fate

| Field | Forwarded To | Dropped At | Verdict |
|---|---|---|---|
| `micro_state` | `AlertDecisionPayload.micro_state` | — | ✅ Fully propagated |
| `micro_present` | `AlertDecisionPayload.micro_present` | — | ✅ Fully propagated |
| `micro_trigger_state` | `AlertDecisionPayload.micro_trigger_state` | — | ✅ Fully propagated |
| `micro_used_for_confirmation` | `AlertDecisionPayload.micro_used_for_confirmation` | — | ✅ Fully propagated |
| `ltf_trigger_state` | `TradePlanEngine.build_plan` (reads via `extensible_context`) | workflow.py boundary | ✅ Intentional — consumed upstream by trade plan, not needed in alert text |
| `internal_mtf_state` | — | workflow.py boundary | ✅ Intentional — fully encoded in `signal_result.setup_state` |
| `cross_frame_aligned` | — | workflow.py boundary | ✅ Intentional — implied by `signal == "LONG"` (all hard gates passed) |
| `consumed_known_at` | — | workflow.py boundary | ⚠️ Dropped — useful for operator debugging, not currently surfaced |
| `regime_snapshot` | — | workflow.py boundary | ⚠️ Dropped — regime context not in `AlertDecisionPayload`; operator must read raw signal |
| `event_risk_snapshot` | — | workflow.py boundary | ⚠️ Dropped — event risk details not in `AlertDecisionPayload` |
| `sector_snapshot` | — | workflow.py boundary | ⚠️ Dropped — sector context not in `AlertDecisionPayload` |
| `hard_gates` | — | workflow.py boundary | ⚠️ Dropped — debug only; not needed in alert text |

## Propagation Chain

```
SignalEngine.evaluate
  → SignalEngineResult.extensible_context
    ↓
    TradePlanEngine.build_plan  ← reads: ltf_trigger_state
    ↓
    AlertWorkflow.evaluate      ← reads: micro_state, micro_present,
                                          micro_trigger_state,
                                          micro_used_for_confirmation
      → AlertDecisionPayload    ← carries: all 4 micro fields above
        ↓
        TelegramRenderer.render ← renders: all 4 micro fields
```

## Risk Assessment

**No active silent-drop bugs.** The 4 micro fields are correctly propagated end-to-end.

The 4 ⚠️ fields (`consumed_known_at`, `regime_snapshot`, `event_risk_snapshot`, `sector_snapshot`) are
intentionally absent from `AlertDecisionPayload`. They are operator-diagnostic fields, not alert-content
fields. If they need to be surfaced for operator triage, the preferred path is:

1. Expose them on the operator web panel by reading `signal_result.extensible_context` directly (before
   the workflow step), or
2. Add them to `AlertDecisionPayload` and extend the renderer with a `Details:` section.

## CLAUDE.md Note

> **Silent drop risk:** Any mapping boundary that does not forward extensible_context values.
> This already caused one production bug. Audit every mapper when adding new fields.

When adding any new field to `SignalEngineResult.extensible_context`, explicitly decide whether it needs
to reach:
1. `TradePlanEngine` (reads directly from `signal_result.extensible_context`)
2. `AlertDecisionPayload` (requires explicit extraction in `AlertWorkflow.evaluate`)
3. Rendered alert text (requires explicit rendering in `TelegramRenderer.render`)
