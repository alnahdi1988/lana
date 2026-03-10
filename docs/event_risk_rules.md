# Event Risk Rules

## 1. Purpose

Event risk can invalidate otherwise strong structural setups.

The system must suppress or penalize setups around major binary events.

---

## 2. Events to monitor

At minimum:
- earnings dates
- major corporate announcements
- guidance releases
- offerings / dilution events
- FDA / regulatory events for biotech or similar names
- trading halts if detectable

---

## 3. Event blackout window

Default rule:
- suppress new long alerts within a configurable window around earnings

Suggested default:
- from 1 trading day before earnings
- until 1 trading day after earnings

This must be configurable.

---

## 4. Event risk classes

Allowed labels:

- `NO_EVENT_RISK`
- `EARNINGS_BLOCK`
- `CORPORATE_EVENT_BLOCK`
- `NEWS_ABNORMAL_RISK`
- `HALT_RISK`

---

## 5. Event handling policy

### Hard block
No alert should be sent if:
- earnings blackout is active
- major binary event block is active

### Soft penalty
Confidence may be reduced if:
- unusual news-driven volume suggests unstable behavior
- event context is unclear but not fully blocked

---

## 6. Data behavior

If event data is unavailable:
- default to conservative behavior where appropriate
- log missing event coverage
- do not silently ignore event risk in production

---

## 7. Signal engine interaction

The signal engine must include:
- `event_risk_blocked: true/false`
- relevant reason code if blocked

Examples:
- `EVENT_RISK_BLOCKED`
- `EARNINGS_BLACKOUT_ACTIVE`
- `CORPORATE_EVENT_BLOCKED`
