# Telegram GATEWAY_ALLOW_ALL_USERS=false — Change Plan
# Status: DRAFT — Do not apply until user approves

---

## 1. Current File Path
`~/.hermes/.env` (live runtime config)

---

## 2. Current Value
```
GATEWAY_ALLOW_ALL_USERS=true
```

---

## 3. Proposed Value
```
GATEWAY_ALLOW_ALL_USERS=false
```

---

## 4. Whether Saleh DMs Will Continue Working
**YES** — if Saleh's user ID (8569633077) is in `TELEGRAM_ALLOWED_USERS`.
Currently: `TELEGRAM_ALLOWED_USERS=8569633077` — confirmed present.

Saleh's primary Telegram account will be unaffected.
Secondary/unknown accounts will be blocked immediately.

---

## 5. Whether Corporate Group Will Continue Working
**DEPENDS** on whether the Corporate group ID (-5233031183) is in `allowed_chat_ids`.

Current `config.yaml` allowed_chat_ids:
```yaml
allowed_chat_ids: [8569633077, -5233031183]
```

The Corporate group (-5233031183) is in the allowed_chat_ids list.
**Corporate group will continue working** after the change.

---

## 6. Exact Test Command / Method

**Before applying (verify current state):**
```bash
grep -n "GATEWAY_ALLOW_ALL_USERS\|TELEGRAM_ALLOWED_USERS" ~/.hermes/.env
grep -n "allowed_chat_ids" ~/.hermes/config.yaml
pgrep -f "hermes.*resume"
```

**Apply change (1-line patch):**
```bash
sed -i 's/GATEWAY_ALLOW_ALL_USERS=true/GATEWAY_ALLOW_ALL_USERS=false/' ~/.hermes/.env
```

**Restart Hermes to pick up new config:**
```bash
# Find current PID
HERMES_PID=$(pgrep -f "hermes.*resume" | head -1)
echo "Current Hermes PID: $HERMES_PID"

# Restart
kill $HERMES_PID
sleep 2
nohup /home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume latest > /home/saleh/.hermes/logs/hermes-agent.log 2>&1 &
sleep 5

# Verify restarted
pgrep -f "hermes.*resume"
```

**Test DM (as Saleh):**
Send any message to @HermesAgentCEOBot from your Telegram.
Expected: Bot responds normally.

**Test Corporate Group:**
Send any message to the Corporate group.
Expected: Bot responds normally.

---

## 7. Expected Success Result
- Only allowed user IDs can DM the bot
- Only allowed chat IDs can use the bot in groups
- Unauthorized users receive rejection message
- Saleh's access is unchanged
- Corporate group access is unchanged
- No downtime beyond restart window (~5-10 seconds)

---

## 8. Rollback Command / File Patch

**Immediate rollback:**
```bash
sed -i 's/GATEWAY_ALLOW_ALL_USERS=false/GATEWAY_ALLOW_ALL_USERS=true/' ~/.hermes/.env
```

**Restart Hermes to apply rollback:**
```bash
HERMES_PID=$(pgrep -f "hermes.*resume" | head -1)
kill $HERMES_PID
sleep 2
nohup /home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume latest > /home/saleh/.hermes/logs/hermes-agent.log 2>&1 &
```

---

## 9. What Happens If Access Breaks

**Symptom:** Bot stops responding to DMs or group messages.

**Likely causes:**
1. `TELEGRAM_ALLOWED_USERS` does not include your user ID
2. `allowed_chat_ids` in config.yaml does not include group ID
3. Hermes did not restart properly

**Recovery steps:**
```bash
# 1. Verify .env state
cat ~/.hermes/.env | grep GATEWAY

# 2. If set to false and causing lockout, immediately revert
sed -i 's/GATEWAY_ALLOW_ALL_USERS=false/GATEWAY_ALLOW_ALL_USERS=true/' ~/.hermes/.env

# 3. Restart Hermes
HERMES_PID=$(pgrep -f "hermes.*resume" | head -1)
kill $HERMES_PID 2>/dev/null || true
sleep 2
nohup /home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume latest > /home/saleh/.hermes/logs/hermes-agent.log 2>&1 &
```

---

## 10. Whether Any Downtime Is Expected

**Yes — approximately 5-10 seconds** during Hermes restart.
No data loss. No database impact. No trade disruption (Doctrine is not live trading).

The bot will be unreachable for the restart window.
After restart, the new GATEWAY_ALLOW_ALL_USERS=false setting takes effect.

---

## Implementation Sequence (when approved)

1. Confirm Saleh is at a terminal with WSL access
2. Take a screenshot of current Telegram group to confirm it works
3. Apply sed command to .env
4. Restart Hermes
5. Test DM from Saleh's Telegram
6. Test Corporate group
7. If both work — change is successful
8. If either fails — immediate rollback and investigate

---
