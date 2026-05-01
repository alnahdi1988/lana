# Doctrine Control Implementation — Rollback Procedures
# Generated: 2026-05-01
# These procedures are DRAFT — do not apply unless approved

---

## 1. Telegram Config (GATEWAY_ALLOW_ALL_USERS)

**Current state:** `GATEWAY_ALLOW_ALL_USERS=true` in `~/.hermes/.env`
**Change:** Set to `false`

**Rollback command:**
```bash
patch ~/.hermes/.env 's/GATEWAY_ALLOW_ALL_USERS=false/GATEWAY_ALLOW_ALL_USERS=true/' --force
```

**Alternative rollback (line-level):**
```bash
sed -i '9s/.*/GATEWAY_ALLOW_ALL_USERS=true/' ~/.hermes/.env
```

**What breaks if change is applied:**
- No Telegram DM access for anyone except allowed_user IDs until Hermes is restarted
- Corporate group MUST have -5233031183 in allowed_chat_ids or they lose access
- Saleh DM from any secondary account is blocked

**How to verify before rollback:**
```bash
grep GATEWAY_ALLOW_ALL_USERS ~/.hermes/.env
grep TELEGRAM_ALLOWED_USERS ~/.hermes/.env
pgrep -f "hermes.*resume"
```

---

## 2. Telegram Token Rotation

**Trigger:** Saleh obtains new token from BotFather
**Location:** `~/.hermes/.env` line 11

**Rollback after rotation:**
```bash
# Old token is void — rollback means requesting another rotation
# There is no rollback to old token — it is permanently invalidated by BotFather
```

**If new token fails to work:**
1. Verify token format in .env: `834475...:` prefix with numeric chat_id
2. Restart Hermes: `pkill -f hermes; hermes --resume latest`
3. Test bot: `curl -s "https://api.telegram.org/bot<NEW_TOKEN>/getMe"`
4. Verify DM: send test message to bot

**Redaction needed after rotation:**
```bash
# Audit logs for old token exposure
grep -r "834475" ~/.hermes/logs/ 2>/dev/null | wc -l
# If count > 0: truncate or archive affected log files
```

---

## 3. tirith_fail_open

**Current state:** Unknown (tirith binary verified, setting not found in .env/config)
**Proposed:** Set `tirith_fail_open=false`

**Rollback:**
```bash
# Remove the setting — reverts to binary default
sed -i '/tirith_fail_open/d' ~/.hermes/.env
```

**If lockout occurs:**
- Boot to WSL safe mode or recovery shell
- Remove tirith from PATH or rename binary
- Restart Hermes
- Access via Telegram DM if GATEWAY_ALLOW_ALL_USERS=false is the cause

---

## 4. Drift-check Alerting

**What was added:** Telegram alert on drift-check failure
**Files modified:** `~/.hermes/doctrine/repo/drift-check.sh`

**Rollback:**
```bash
# Restore original drift-check.sh
cd /mnt/d/Doctrine/structure-doctrine-engine
git checkout HEAD -- hermes/doctrine/repo/drift-check.sh
```

**If alert delivery fails repeatedly:**
- Check `~/.hermes/doctrine/drift.log` for curl errors
- Verify TELEGRAM_BOT_TOKEN env var is set: `echo $TELEGRAM_BOT_TOKEN`
- Confirm bot is reachable: `curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"`

---

## 5. Approval Log (JSONL)

**What was created:** `~/.hermes/doctrine/approval-log.jsonl`
**Rollback:**
```bash
# Remove the new log file only — does not affect historical data
rm ~/.hermes/doctrine/approval-log.jsonl
```

**If log grows too large:**
```bash
# Archive and start new log
mv ~/.hermes/doctrine/approval-log.jsonl ~/.hermes/doctrine/approval-log-$(date +%Y%m%d).jsonl
# Re-create empty structure
echo '{"spec":"1.0","type":"doctrine-approval-log","company":"Doctrine Ltd.","description":"Immutable append-only log of all governance decisions. Each entry is a JSON line. Entries are never deleted or modified.","fields":["timestamp","company","decision_category","requested_action","approval_status","approver","source_command","affected_file_config","before_state","after_state","rollback_reference","commit_hash","incident_reference"],"entries":[]}' > ~/.hermes/doctrine/approval-log.jsonl
```

---

## 6. Systemd Service / Autostart

**What was drafted:** `~/.hermes/doctrine/draft/hermes-agent.service` and timer files

**If service fails after enablement:**
```bash
# Disable immediately
sudo systemctl disable hermes-agent.service
sudo systemctl stop hermes-agent.service

# Verify Hermes is NOT running (was manually started)
pgrep -f "hermes.*resume"

# Restart manually
/home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume latest
```

**If machine enters boot loop:**
1. Boot to WSL recovery: `wsl --shutdown`
2. Edit service file to add `ExitOnFailure=false`
3. Or rename service: `mv /etc/systemd/system/hermes-agent.service /etc/systemd/system/hermes-agent.service.disabled`

---

## 7. Git Commit Batches

**Rollback for already-committed changes:**
```bash
cd /mnt/d/Doctrine/structure-doctrine-engine

# Find the last good commit before batch
git log --oneline -10

# Soft reset to undo commits but keep file changes
git reset --soft HEAD~1

# Or hard reset (deletes changes — use with caution)
# git reset --hard HEAD~1
```

**For staged-but-not-committed files:**
```bash
git status
git restore --staged <file>
```

---

## 8. Health Check Cron

**What was added:** Hourly cron job for health-check.sh
**Location:** crontab entry: `0 * * * *`

**Rollback:**
```bash
crontab -l | grep -v "health-check.sh"
# Review output, then replace crontab
crontab -l | grep -v "health-check.sh" | crontab -
```

**Or edit crontab directly:**
```bash
crontab -e
# Delete the health-check.sh line
```

---

## 9. Command Auth Model

**What was documented:** `~/.hermes/doctrine/draft/command-auth-model.md`
**Rollback:** Remove the draft file
```bash
rm ~/.hermes/doctrine/draft/command-auth-model.md
```
