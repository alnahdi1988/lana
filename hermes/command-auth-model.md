# Telegram Command Authentication Model
# Status: DESIGN DOC — Implementation requires A4 approval

---

## Overview

Minimum viable authentication model for Telegram command access.
All Telegram commands pass through this auth layer before execution.

---

## 1. Allowed User ID Validation

**Rule:** Only users in `TELEGRAM_ALLOWED_USERS` can issue any command.

**Current allowed users:**
- `8569633077` (Saleh — primary)

**Implementation:**
```
IF user_id NOT IN TELEGRAM_ALLOWED_USERS:
    REJECT with "Unauthorized user"
    LOG attempt to approval-log.jsonl
    ALERT Saleh via Telegram
```

**In config.yaml:**
```yaml
allowed_user_ids: [8569633077]
```

---

## 2. Allowed Group / Channel Validation

**Rule:** Bot only responds in allowed chat IDs (groups, channels).

**Current allowed chats:**
- `-5233031183` (Corporate group)

**Implementation:**
```
IF chat_id NOT IN allowed_chat_ids:
    IGNORE (do not respond)
    LOG to approval-log.jsonl
```

**In config.yaml:**
```yaml
allowed_chat_ids: [8569633077, -5233031183]
```

---

## 3. Command Whitelist

**Rule:** Only documented commands are processed. All others are rejected.

**Allowed commands (v1):**
| Command | Description | Risk Level |
|---|---|---|
| `/status` | Return bot health and config summary | LOW |
| `/ping` | Liveness check | LOW |
| `/help` | Return command list | LOW |
| `/health` | Run health-check.sh, return summary | LOW |
| `/drift` | Run drift-check.sh, return summary | LOW |
| `/log` | Return last N lines of gateway log | MEDIUM |
| `/reload` | Reload config (requires confirmation) | HIGH |
| `/approve <action>` | Approve a pending high-risk action | HIGH |

**Blocked commands (never supported in v1):**
- Any command containing `api_key`, `secret`, `password`, `token`
- Any command that starts a trade, places an order, or modifies positions
- Any command that accesses Binance, Coinbase, or any exchange API
- Any command that modifies .env, config.yaml, or SOUL.md

---

## 4. High-Risk Command Approval Requirement

**Rule:** HIGH risk commands require explicit approval before execution.

**High-risk commands:**
- `/reload` — reloads configuration
- `/approve` — approves a pending action
- Any command that touches trading, positions, or capital

**Flow:**
```
USER sends /reload
BOT responds: "Reload is HIGH RISK. Type /confirm_reload to proceed."
USER sends /confirm_reload
BOT: Requires Saleh user ID (8569633077) OR Corporate group consensus
    IF authorized: Execute reload, LOG to approval-log.jsonl
    IF not authorized: REJECT, ALERT Saleh
```

**Alternative:** Require approval from a secondary channel (e.g., SMS code, email link)

---

## 5. No Live Trading Command Support (v1)

**Rule:** No Telegram command can trigger a live trade, place an order, or modify positions.

**Rationale:** Trading must go through the proper pipeline with all risk controls in place.
Telegram is an information channel only for trading — not a trading terminal.

**Implementation:**
```
IF command contains any trading-related keyword:
    REJECT: "Trading commands are not supported via Telegram. Use the trading platform."
```

---

## 6. No API-Key Command Support (v1)

**Rule:** Users cannot set, view, or modify API keys via Telegram.

**Implementation:**
```
IF command contains "api_key", "secret", "token", "password":
    REJECT: "API key operations are not available via Telegram."
    LOG to approval-log.jsonl with redacted values
```

---

## 7. Logging to Approval Log

**All** auth events are logged to `~/.hermes/doctrine/approval-log.jsonl`:

```json
{"timestamp":"2026-05-01T12:00:00Z","company":"Doctrine","decision_category":"telegram_auth","requested_action":"/reload","approval_status":"rejected","approver":"hermes_auth","source_command":"/reload","affected_file_config":"config.yaml","before_state":"user_id=unknown","after_state":"rejected_unauthorized_user","rollback_reference":"N/A","commit_hash":"","incident_reference":"auth_reject_001"}
```

---

## 8. Rejection Message for Unauthorized Users

**DM rejection (unknown user):**
> "❌ Unauthorized. Your Telegram ID is not registered with this bot. Contact the operator."

**Group rejection (unknown group):**
> (No response — bot ignores unauthorized groups silently to avoid info leakage)

**High-risk command rejection:**
> "⚠️ High-risk command requires operator approval. Request denied."

---

## 9. Alert Saleh on Unauthorized Command Attempt

**Trigger:** Any command from non-allowed user OR any high-risk command attempt.

**Alert format (Telegram DM to Saleh):**
> "🚨 Unauthorized command attempt\nUser: [user_id]\nCommand: [command]\nChat: [chat_id]\nTime: [timestamp]"

**Rate limit:** Max 1 alert per minute per user to avoid spam.

---

## Auth Flow Diagram

```
Telegram Message Received
         |
         v
   [Extract user_id, chat_id, command]
         |
         v
   Is user_id in allowed_user_ids?
    /                            \
   NO                            YES
    |                              |
    v                              v
  [REJECT]              Is chat_id in allowed_chat_ids?
  + ALERT Saleh          /                          \
                        NO                          YES
                         |                            |
                         v                            v
                    [IGNORE]              Is command in whitelist?
                     (silent)              /                            \
                                          NO                            YES
                                           |                              |
                                           v                              v
                                     [REJECT]              Is command HIGH RISK?
                                      "Unknown               /                  \
                                      command"               NO                  YES
                                                              |                    |
                                                              v                    v
                                                       [EXECUTE]           [REQUIRE APPROVAL]
                                                                           /              \
                                                                     NO                YES
                                                                      |                  |
                                                                      v                  v
                                                                [EXECUTE]        [QUEUE FOR
                                                                                  SALEH APPROVAL]
```

---

## Implementation Requirements

**Files to modify:**
- `~/.hermes/config.yaml` — add allowed_user_ids, command_whitelist
- `~/.hermes/.env` — add TELEGRAM_ALLOWED_USERS (already present)
- Hermes gateway — add auth middleware (requires A4 approval)

**This is a design document.** Actual implementation requires:
1. Hermes gateway access (to add auth middleware)
2. A4 approval for config changes
3. Testing in a non-production environment first
