# Signal Contract

This document defines the exact contract for the signal engine.

## 1. Purpose

The signal engine outputs only:

- `LONG`
- `NONE`

No short signals.
No trade execution.
No sizing.

The signal engine decides whether a stock currently presents a valid doctrine-based long opportunity.

---

## 2. Inputs

Required inputs:

- symbol
- latest bars for:
  - 4H
  - 1H
  - 15M
- optional 5M micro confirmation
- universe eligibility
- regime state
- sector context
- event-risk flag
- doctrine features and structural events

---

## 3. Output schema

```json
{
  "symbol": "UAMY",
  "timestamp": "2026-03-08T15:45:00Z",
  "signal": "LONG",
  "confidence": 0.81,
  "grade": "A",
  "bias_htf": "BULLISH",
  "setup_state": "RECONTAINMENT_CONFIRMED",
  "reason_codes": [
    "PRICE_RANGE_VALID",
    "UNIVERSE_ELIGIBLE",
    "HTF_BULLISH_STRUCTURE",
    "MTF_DISCOUNT_RESPONSE",
    "LTF_BULLISH_CHOCH",
    "CROSS_FRAME_ALIGNMENT",
    "REGIME_ALLOWED"
  ],
  "event_risk_blocked": false
}
```

If invalid:

```json
{
  "symbol": "ONDS",
  "timestamp": "2026-03-08T15:45:00Z",
  "signal": "NONE",
  "confidence": 0.29,
  "grade": "IGNORE",
  "bias_htf": "NEUTRAL",
  "setup_state": "NO_VALID_LONG_STRUCTURE",
  "reason_codes": [
    "PRICE_RANGE_VALID",
    "UNIVERSE_ELIGIBLE",
    "HTF_UNCLEAR",
    "NO_CROSS_FRAME_CONFIRMATION"
  ],
  "event_risk_blocked": false
}
```

## 4. Required fields

`symbol`
Ticker.

`timestamp`
Timestamp at which the signal becomes known using delayed data assumptions.

`signal`
Must be exactly one of:
- `LONG`
- `NONE`

`confidence`
A float between `0.0` and `1.0`.

`grade`
Must be one of:
- `A+`
- `A`
- `B`
- `IGNORE`

`bias_htf`
Must be one of:
- `BULLISH`
- `NEUTRAL`
- `BEARISH`

`setup_state`
Examples:
- `RECONTAINMENT_CONFIRMED`
- `DISCOUNT_RESPONSE`
- `EQUILIBRIUM_HOLD`
- `NO_VALID_LONG_STRUCTURE`
- `INVALIDATED`

`reason_codes`
Machine-readable reasons.

`event_risk_blocked`
Boolean.

---

## 5. Signal decision rules

A stock may return `LONG` only if all of these are true:

- universe eligibility passes
- price is between $5 and $50
- HTF bias is bullish
- MTF is in a valid bullish setup state
- LTF has a valid bullish trigger
- cross-frame alignment exists
- event-risk suppression is not active
- regime allows long continuation or reclaim behavior
- confidence reaches configured threshold

The engine prefers `NONE` if ambiguity remains.

---

## 6. Confidence philosophy

Confidence is not prophecy.
Confidence is a quality score.

It should combine:

- HTF strength
- MTF setup quality
- LTF trigger quality
- cross-frame alignment
- zone location quality
- regime support
- sector support
- event-risk penalties
- structural cleanliness

---

## 7. Grade thresholds

Suggested initial mapping:

- `A+` = confidence >= 0.90
- `A` = confidence >= 0.80
- `B` = confidence >= 0.70
- `IGNORE` = below 0.70

These must be configurable.

Telegram policy:
- only `A+` and `A` are sent

---

## 8. Reason codes

Allowed examples:

- `PRICE_RANGE_VALID`
- `UNIVERSE_ELIGIBLE`
- `UNIVERSE_REJECTED`
- `HTF_BULLISH_STRUCTURE`
- `HTF_UNCLEAR`
- `HTF_BEARISH`
- `MTF_DISCOUNT_RESPONSE`
- `MTF_EQUILIBRIUM_HOLD`
- `MTF_RECONTAINMENT_CONFIRMED`
- `MTF_INVALIDATED`
- `LTF_BULLISH_CHOCH`
- `LTF_BULLISH_BOS`
- `LTF_BULLISH_RECLAIM`
- `FAKE_BREAKDOWN_REVERSAL`
- `TRAP_REVERSE_BULLISH`
- `CROSS_FRAME_ALIGNMENT`
- `NO_CROSS_FRAME_CONFIRMATION`
- `REGIME_ALLOWED`
- `REGIME_BLOCKED`
- `SECTOR_WEAK`
- `EVENT_RISK_BLOCKED`
- `EXTENDED_FROM_EQUILIBRIUM`
- `CHOP_REGIME`
- `LOW_STRUCTURAL_QUALITY`

Codex may extend this list carefully, but not replace the logic.

---

## 9. Delayed data rule

The signal timestamp must reflect when the setup becomes known given Polygon's 15-minute delay.

Backtests and dry runs must use the same assumption.

No same-bar fantasy fills.
No pretending intrabar knowledge existed.

---

## 10. Non-goals

The signal contract does not include:

- position size
- broker order
- execution
- PnL
- portfolio logic
- short logic
