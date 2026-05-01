# Doctrine Closure Control Pass Report
**Date:** 2026-05-01 | **Profile:** doctrine | **Status:** IN PROGRESS

---

## 1. PRIORITY ORDER COMPLETED

All 9 items reviewed in order. Full report below.

---

## 2. P0 SECURITY CONTROL REVIEW

### 2.1 GATEWAY_ALLOW_ALL_USERS=true

**Current state:**
- `GATEWAY_ALLOW_ALL_USERS=true` in `~/.hermes/.env` (line 9)
- Same flag implied in `~/.hermes/config.yaml` (allowed_chat_ids only restricts group responses, not DMs)
- `allowed_chat_ids: [8569633077, -5233031183]` — user ID and group ID — but this does NOT block DMs from other users

**File:** `~/.hermes/.env` line 9

**Risk:** CRITICAL — Any Telegram user can DM `@HermesAgentCEOBot` and issue commands. No authentication on incoming messages. If the bot token is exposed, an attacker has full Hermes access.

**Recommended fix:**
```
# In ~/.hermes/.env:
GATEWAY_ALLOW_ALL_USERS=false
```
Then ensure `allowed_chat_ids` contains only `8569633077` (your user ID). The gateway will reject all DMs except from allowed users.

**Autonomous fix possible:** Yes — I can change the .env file now.

**Saleh approval required:** Yes — per constitution A4 item 17 (changing allowed Telegram users) and item 18 (changing SOUL.md authority rules). This is an access-control change that could lock you out if the allowed_chat_ids is wrong.

**Rollback method:**
```
# Rollback: restore GATEWAY_ALLOW_ALL_USERS=true
patch ~/.hermes/.env 'GATEWAY_ALLOW_ALL_USERS=false' 'GATEWAY_ALLOW_ALL_USERS=true'
```
Then restart Hermes gateway.

**Test after fix:**
1. From a non-allowed Telegram account, DM `@HermesAgentCEOBot` — expect no response
2. From your account (8569633077), DM the bot — expect normal response
3. Check `gateway.log` for any `ACCESS DENIED` or rejection entries

**Will DMs still work for Saleh after change?** Yes — `8569633077` is in `allowed_chat_ids`. Your DMs will continue working.

---

### 2.2 tirith_fail_open=true

**Current state:** `tirith_fail_open: true` in `~/.hermes/config.yaml` line 289

**What Tirith controls:** Unknown. Binary at `~/.hermes/bin/tirith` — stripped ELF binary, no readable strings revealing purpose. Agent logs show it was installed as a security layer with SHA-256 verification on 2026-04-06. Appears to gate or approve requests based on some policy.

**What happens if Tirith times out:** With `tirith_timeout: 5` and `tirith_fail_open: true`, if Tirith fails or times out within 5 seconds, the request is ALLOWED through.

**Risk of fail-open:** If Tirith is a security policy enforcement layer (secrets detection, command approval, access control), then a timeout or crash means ALL security gates are bypassed. Attacker could potentially issue commands that would normally be blocked.

**Impact of changing to false:** If Tirith times out or fails, requests would be DENIED instead of allowed. This is safer but could cause legitimate operations to be blocked if Tirith is unstable.

**Possible lockout risk:** If Tirith crashes and `tirith_fail_open=false`, ALL requests would be denied until Tirith is restarted. This could lock both of us out.

**Recommended decision:** Defer to Saleh. The unknown nature of Tirith makes this a judgment call. If Tirith is a critical security gate, `fail_open=true` is a serious vulnerability. If it's advisory-only, the risk is lower. Need Saleh's context on what Tirith actually does.

**Autonomous fix possible:** Yes — can change config.

**Saleh approval required:** Yes — per A4 item 18 (changing security settings). This changes the security posture materially.

**Rollback method:** `patch config.yaml 'tirith_fail_open: false' 'tirith_fail_open: true'` — no restart needed if Hermes reads config dynamically.

**Test plan:** Monitor behavior for 24h after change. If legitimate commands start being rejected, Tirith may be unstable and rollback may be needed.

---

### 2.3 Exposed Telegram Token

**Current state:**
- Active bot token visible in:
  - `~/.hermes/.env` line 11 (TELEGRAM_BOT_TOKEN)
  - `~/.hermes/config.yaml` line 269 (bot_token, redacted by redact_secrets: true)
  - `~/.hermes/doctrine/repo/health-check.sh` line 9 (token in TELEGRAM_BOT_TOKEN variable)
  - Possibly in git history (searched git log — last 3 commits do not expose token)

**Files affected:** `~/.hermes/.env`, `~/.hermes/config.yaml`, `~/.hermes/doctrine/repo/health-check.sh`, `/mnt/d/Doctrine/structure-doctrine-engine/.openclaw/openclaw.json`

**Risk:** Token in .env is somewhat protected (file permissions), but if the repo is pushed to a public or shared remote, the token in openclaw.json and .env.example would be exposed. The token in health-check.sh is in a git-tracked file.

**Recommended fix:**
1. Rotate token via @BotFather — get new token
2. Update `.env` with new token
3. Update `health-check.sh` with new token
4. Delete old token
5. Never commit tokens to git — ensure `.env` is in `.gitignore`
6. Verify git history doesn't contain the old token string

**Autonomous fix possible:** Partial — can update files, but token rotation requires BotFather interaction from you.

**Saleh approval required:** Yes — per A4 item 15 (rotating production bot tokens).

**Rollback method:** If rotated, old token cannot be restored unless you keep it. Store old token securely if rollback may be needed.

**Test method:** After rotation, verify old token no longer works and new token responds correctly.

---

### 2.4 No Telegram Command Authentication

**Current state:** No command authentication model exists. Any allowed user can send any command. The `command_allowlist` in config.yaml (line 280-281) only covers "script execution via -e/-c flag" — no per-command auth.

**Files:** `~/.hermes/config.yaml` lines 280-282

**Risk:** If GATEWAY_ALLOW_ALL_USERS is ever fixed but a command auth model isn't built, any allowed user can issue any command including `shell`, `exec`, file writes, etc.

**Recommended fix:** Implement minimum command auth:
1. Define a command allowlist in config.yaml
2. Commands not on the allowlist require explicit approval
3. Use the existing `approvals.mode: manual` — when a non-whitelisted command is received, Hermes asks for approval before executing
4. Or: use a command prefix model where only commands starting with `/approve <command>` are auto-approved

**Autonomous fix possible:** Partial — can draft the config change. Requires Saleh approval per A4.

**Saleh approval required:** Yes — per A4 item 18 (changing command authority).

**Rollback method:** Restore previous command_allowlist in config.yaml.

**Test method:** Send a non-whitelisted command and verify approval prompt is returned.

---

### 2.5 No Immutable Approval Log

**Current state:** No tamper-evident log exists. All logs are editable markdown files in `~/.hermes/logs/`. Decisions, approvals, and commands are recorded in session snapshots and WORK_QUEUE.md — all editable.

**Files affected:** `~/.hermes/logs/agent.log`, `~/.hermes/logs/gateway.log`, `~/.hermes/WORK_QUEUE.md`, `~/.hermes/STATE.md`

**Risk:** If an attacker or rogue process gains filesystem access, they can alter logs to hide evidence. If I make an error, I could theoretically modify logs to obscure it.

**Recommended fix:** See Section 5 (Approval Log Design) below.

**Autonomous fix possible:** Yes — can design and implement the log.

**Saleh approval required:** Yes — per A4 item 18 and Section 8.2 improvements requiring approval (deleting/rewriting logs). However, building an immutable log is different from deleting logs — I recommend asking for approval to implement, not just patching in.

**Rollback method:** If SQLite/JSONL is used, rollback means truncating or patching the log file — not truly immutable. Design choice matters here.

---

### 2.6 No Verified Systemd Autostart

**Current state:**
- No systemd user service exists
- Hermes runs manually: `/home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume`
- Started via saleh user's shell or terminal session
- No `systemctl --user status hermes` — "Unit hermes.service could not be found"

**Files:** None (service file does not exist)

**Risk:** If the server reboots, Hermes does NOT auto-restart. No automatic recovery. Saleh must manually start it.

**Recommended fix:** Create systemd user service file. See Section 7.

**Autonomous fix possible:** Yes — can draft the service file.

**Saleh approval required:** Yes — per A4 item 20 (enabling systemd autostart for live services).

**Rollback method:** `systemctl --user disable hermes` or delete service file.

**Test method:** `systemctl --user start hermes` and verify process starts. Cannot test reboot behavior without actually rebooting (per instruction).

---

### 2.7 No Gateway Restart Automation

**Current state:** No automation for gateway restart. If Hermes crashes, I can detect it (health-check.sh checks PID) but cannot restart it.

**Files:** `~/.hermes/doctrine/repo/health-check.sh` (detects only), `~/.hermes/config.yaml`

**Risk:** If Hermes crashes and neither of us is watching, the system is down with no automatic recovery.

**Recommended fix:** Two parts:
1. Systemd service with Restart=always policy (handles crash recovery)
2. Health-check cron that alerts on Hermes death (already exists — line 43 in health-check.sh alerts but doesn't restart)

**Autonomous fix possible:** Partial — can draft systemd service. Restart-on-crash is enabled via systemd Restart=always.

**Saleh approval required:** Yes — per A4 item 20.

**Rollback method:** `systemctl --user stop hermes && systemctl --user disable hermes`

---

### 2.8 No Rollback Process

**Current state:** No documented rollback procedure exists. Git is the only version control. No snapshots of config state before changes.

**Files:** None (gap in process)

**Risk:** If a change breaks Hermes or causes data loss, there is no documented way to recover previous known-good state.

**Recommended fix:**
1. Document rollback procedure: `git checkout <commit-hash> -- <file>` to restore specific files
2. Before any config change, create a git commit snapshot: `git add <file> && git commit -m "backup: <description>"`
3. Use git tags for known-good milestones
4. Document procedure in `~/.hermes/doctrine/repo/ROLLBACK.md`

**Autonomous fix possible:** Yes — can write rollback documentation.

**Saleh approval required:** No — documentation is A3 (apply low-risk documentation fixes). However, implementing actual rollback for a specific broken change requires separate approval at that time.

**Rollback method:** Depends on what broke. Generally: `git log`, find last good commit, `git checkout <hash> -- <file>`.

**Test method:** Test rollback procedure on a non-critical file before it's needed in anger.

---

## 3. TELEGRAM ACCESS CONTROL HARDENING PLAN

### Current Architecture

| Item | Value |
|------|-------|
| Active bot | @HermesAgentCEOBot |
| Bot token (redacted) | `834475...Mk0I` |
| Bot token source | `~/.hermes/.env` line 11 |
| Your user ID | `8569633077` |
| Corporate group ID | `-5233031183` |
| allowed_chat_ids | `[8569633077, -5233031183]` |
| GATEWAY_ALLOW_ALL_USERS | `true` (in `.env` line 9) |
| Bot token also in | `~/.hermes/doctrine/repo/health-check.sh` line 9 |
| Bot token also in | `/mnt/d/Doctrine/.../.openclaw/openclaw.json` |

### Current Access Model

- DMs: OPEN to any Telegram user (`GATEWAY_ALLOW_ALL_USERS=true`)
- Group: RESTRICTED to users in `allowed_chat_ids` (only `-5233031183` group allowed)
- Command auth: NONE — any allowed user can issue any command

### Recommended Final Value

```
# ~/.hermes/.env
GATEWAY_ALLOW_ALL_USERS=false
```

```
# ~/.hermes/config.yaml — allowed_chat_ids (already correct)
allowed_chat_ids:
  - 8569633077   # your user ID
  - -5233031183  # Corporate group
```

### Will DMs Still Work for Saleh?

YES. Your user ID `8569633077` is in `allowed_chat_ids`. With `GATEWAY_ALLOW_ALL_USERS=false`, DMs from you will continue working. DMs from anyone else will be rejected.

### How to Test After Change

1. Have a friend try to DM the bot — should get no response
2. You DM the bot — should respond normally
3. Check `gateway.log` for `[ACCESS DENIED]` entries from unknown users
4. Send a command from your account — should work

### How to Rollback If Access Breaks

```bash
# One-line rollback:
patch ~/.hermes/.env 'GATEWAY_ALLOW_ALL_USERS=false' 'GATEWAY_ALLOW_ALL_USERS=true'
```

No restart needed if Hermes reads .env dynamically. If it doesn't:
```bash
# Find Hermes PID
pgrep -f "hermes.*resume"
# Kill it
kill <PID>
# Restart manually (until systemd is set up)
~/.hermes/hermes-agent/venv/bin/python3 ~/.local/bin/hermes --resume
```

### Command Authentication

Currently no command auth model exists.

**Minimum command-auth model recommendation:**

Option A (simplest — allowlist): Only these commands are auto-approved:
- `status` — system status
- `health` — health check result
- `queue` — show work queue
- `help` — help

Everything else triggers an approval prompt: "This command requires your approval. Reply /approve <command> to proceed."

Option B (role-based — for future): Assign command roles. Admin commands require explicit `/approve`. Standard commands auto-approve.

**Recommended:** Option A — minimum viable, can implement now.

---

## 4. TIRITH FAIL-OPEN CONTROL

### What Tirith Appears to Control

Unknown from source inspection. Binary is stripped. Agent log on 2026-04-06 says: "cosign not on PATH — installing tirith with SHA-256 verification only." Tirith was installed as a security layer. Possible functions:
- Secrets detection in files/messages
- Request approval/rejection based on policy
- Gating API calls or command execution
- Scanning for exposed tokens/API keys

### What Happens If Tirith Times Out

With `tirith_timeout: 5` and `tirith_fail_open: true`: requests are ALLOWED after 5 seconds of Tirith silence.

With `tirith_fail_open: false`: requests would be DENIED after 5 seconds of Tirith silence.

### Risk of Fail-Open

If Tirith enforces security policy, fail-open means:
- Security gates bypassed during Tirith downtime
- Potential for commands to execute without security scanning
- If Tirith crashes, ALL requests pass through

### Impact of Changing to false

- Safer default — unknown/trusted requests are denied rather than allowed
- Could cause legitimate requests to be blocked if Tirith is slow or unstable
- If Tirith dies completely, Hermes becomes inoperable (all requests denied)
- This is the safer setting for a security layer, but only if Tirith is reliable

### Possible Lockout Risk

HIGH. If Tirith crashes and `tirith_fail_open=false`, no requests get through. This would lock both you and me out of Hermes. Only manual intervention (fixing Tirith or setting back to `true`) would restore access.

### Recommended Decision

**DEFER** — do not change without understanding what Tirith does. Options:
1. Find documentation on Tirith's purpose before changing
2. If Tirith is critical infrastructure, set up monitoring so we know if it's unstable
3. Consider adding a Tirith health check to health-check.sh before changing fail_open

**If the security team (or instinct) says "fail-open is wrong," I recommend:**
1. First add Tirith to health-check.sh so we know if it's alive
2. Run for 24h to assess stability
3. Then change to `tirith_fail_open: false`

**Autonomous fix possible:** Yes — can change config.yaml.

**Saleh approval required:** Yes — A4 item 18.

---

## 5. IMMUTABLE APPROVAL LOG DESIGN

### Requirements

Must record: timestamp, company, decision category, requested action, approval status, approver, command/source, file/config affected, before state, after state, rollback reference, related commit hash, incident reference.

### Options Analysis

| Option | Pros | Cons | Doctrine Fit |
|--------|------|------|-------------|
| A. Append-only markdown | Simple, human-readable, git-backed | Not programmatically tamper-evident, can be edited | Good for now |
| B. SQLite approval ledger | Structured queries, small, portable | Requires new dependency, not human-readable | Good option |
| C. JSONL append-only log | Structured, easy to parse, git-compatible | Requires parsing logic | Good option |
| D. Git-backed decision log | Git history is immutable, hash-chained | Git history can be rewritten with force-push | Moderate |
| E. Hash-chained tamper-evident log | Cryptographically tamper-evident | Complex to implement, overkill for current scale | Future |

### Recommendation: Option C — JSONL Append-Only Log

**Why:**
- Simple to implement (Python stdlib: `json.dumps` + `open(append)`)
- Structured and queryable (can grep, can load into any JSON parser)
- Human-readable for debugging (one JSON object per line)
- Easy to rotate (start new file per month)
- Git-compatible (line-based diffs work)
- NOT overengineered for current scale

**Schema:**
```json
{"ts":"2026-05-01T19:54:00+03:00","company":"doctrine","category":"security","action":"GATEWAY_ALLOW_ALL_USERS change","status":"approved","approver":"saleh","source":"telegram:8569633077","files":["~/.hermes/.env"],"before":"GATEWAY_ALLOW_ALL_USERS=true","after":"GATEWAY_ALLOW_ALL_USERS=false","rollback":"patch ~/.hermes/.env 'GATEWAY_ALLOW_ALL_USERS=false' 'GATEWAY_ALLOW_ALL_USERS=true'","commit":"aff253b","incident":null}
```

**Location:** `~/.hermes/logs/approvals.jsonl`

**Autonomous implementation:** Yes — can implement without Saleh approval as it's a new log file, not a change to existing logs or security settings. However, per constitution Section 8.2, deleting/rewriting logs requires approval. This is a new log, not rewriting existing — I consider this A3 (apply low-risk documentation/logging improvements). If uncertain, I'll ask.

---

## 6. HEALTH AND DRIFT AUTOMATION PLAN

### Current State

- `health-check.sh` exists at `~/.hermes/doctrine/repo/health-check.sh` — checks Hermes PID, memory, disk, Telegram, gateway errors, agent errors
- `drift-check.sh` exists at `~/.hermes/doctrine/repo/drift-check.sh` — checks SOUL sync, Telegram binding, __REPO_ROOT__ tokens
- Neither is automated — must be run manually
- health-check.sh has Telegram alert on failure (lines 24-26)
- drift-check.sh has no alert on failure (exits 1, no notification)

### Recommended Automation

**Option:** systemd user timer (better than cron for this system — cron exists but systemd timers are more robust)

**Schedule:**
- health-check: every hour (systemd timer)
- drift-check: every 6 hours (systemd timer)

**Files:**
- Service: `~/.config/systemd/user/hermes-health.service`
- Timer: `~/.config/systemd/user/hermes-health.timer`
- drift service/timer similar

**Alert on failure:**
- health-check.sh already sends Telegram alert on failure
- drift-check.sh needs alert addition — should send Telegram on failure (P0 trigger per constitution Section 7)

**Log location:** `~/.hermes/doctrine/health.log` (health), `~/.hermes/doctrine/drift.log` (drift)

**Escalation:** If health-check fails → Telegram alert (already implemented). If drift-check fails → should escalate to P1.

**Cron vs systemd timer:**
- systemd preferred — survives user session drops, better restart behavior
- If systemd is not available for user services in WSL, fall back to cron

**Test method:** `systemctl --user start hermes-health.timer && sleep 5 && systemctl --user status hermes-health.timer`

**Rollback:** `systemctl --user stop hermes-health.timer && systemctl --user disable hermes-health.timer`

**Can implement autonomously:** Yes — service files are A3 (low-risk operational improvements). Adding drift-check Telegram alert is A3. This is within my autonomous scope.

---

## 7. SYSTEMD / AUTOSTART VERIFICATION

### Current State

| Item | Status |
|------|--------|
| Process manager | Manual terminal session |
| Hermes PID | 25854 (started with `hermes --resume`) |
| systemd user service | Does NOT exist |
| systemd global service | Does NOT exist |
| Hermes binary | `/home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes` |
| Restart policy | None — if it dies, it stays dead |

**System info:** WSL (Windows Subsystem for Linux), systemd may not be fully functional in WSL user sessions.

### Can Systemd User Services Run in WSL?

WSL does not run systemd by default as PID 1. However, `systemctl --user` can work if:
- `systemd` is running as a user session daemon, OR
- WSL has systemd enabled (`systemctl --user` works in newer WSL versions)

Current test: `systemctl --user status hermes` returns "Unit could not be found" — user services don't exist yet.

### Recommended Service File (when systemd is available)

```
~/.config/systemd/user/hermes.service:
[Unit]
Description=Hermes AI Agent
After=network.target

[Service]
Type=simple
User=%u
WorkingDirectory=/home/saleh
ExecStart=/home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume
Restart=always
RestartSec=10
StandardOutput=append:/home/saleh/.hermes/logs/hermes-stdout.log
StandardError=append:/home/saleh/.hermes/logs/hermes-stderr.log

[Install]
WantedBy=default.target
```

**Enable:** `systemctl --user enable hermes && systemctl --user start hermes`

**Autonomous fix possible:** Yes — can draft the service file.

**Saleh approval required:** Yes — per A4 item 20 (enabling systemd autostart).

**Risk of enabling:** If the service file has an error, Hermes won't start on reboot and you'll need to manually fix. Test thoroughly before relying on it.

**Test method:** `systemctl --user start hermes` and verify PID appears. Cannot test reboot behavior without rebooting (per instruction).

**Rollback:** `systemctl --user disable hermes && systemctl --user stop hermes`

---

## 8. GIT STATUS CLASSIFICATION

### Modified Files — Classification

**BATCH 1 — Security / Governance (commit: "security hardening: access control and monitoring")**
Files: (none in modified — these are all new files to commit)

**BATCH 2 — Operating Constitution / Governance (READY TO COMMIT)**
Files:
- `hermes/operating-constitution.md` ← already committed in aff253b
- `hermes/HERMES_SOUL.md` ← already committed in 0734653

**BATCH 3 — OpenClaw Config (commit: "update OpenClaw runtime config")**
- `.openclaw/MISSION_CONTROL.md` — OpenClaw mission control doc
- `.openclaw/cron/jobs.json` — OpenClaw cron config
- `.openclaw/openclaw.json` — OpenClaw runtime binding config

**BATCH 4 — Health/Drift Scripts (commit: "add health-check and drift-check scripts")**
- `~/.hermes/doctrine/repo/health-check.sh` — NOT in repo (lives in ~/.hermes/, not repo)
- `~/.hermes/doctrine/repo/drift-check.sh` — NOT in repo
Note: These live in `~/.hermes/` not in the repo. They are operational scripts, not Doctrine engine code.

**BATCH 5 — Role Documentation (commit: "add role skills documentation")**
- `AGENTS.md` — agent role definitions (may overlap with role-skills-documentation.md)

**BATCH 6 — Test Files (commit: "update test coverage")**
- `tests/alerts/test_workflow_decision.py`
- `tests/config/test_settings.py`
- `tests/engines/test_signal_engine_bias_and_setup.py` ← NEW file (wasn't in original list)
- `tests/engines/test_trade_plan_engine_gating.py`
- `tests/engines/test_trade_plan_engine_invalidation_targets.py`
- `tests/learning/test_ml_pipeline.py`
- `tests/product/test_cli.py`
- `tests/product/test_control.py`
- `tests/product/test_doctrine_tracking.py`
- `tests/product/test_launcher.py`
- `tests/product/test_service.py`
- `tests/product/test_state.py`
- `tests/product/test_web.py`

**BATCH 7 — Core Engine (commit: "update core engine models and config")**
- `src/doctrine_engine/__init__.py`
- `src/doctrine_engine/config/__init__.py`
- `src/doctrine_engine/config/settings.py`
- `src/doctrine_engine/db/__init__.py`
- `src/doctrine_engine/db/base.py`
- `src/doctrine_engine/db/models/__init__.py`
- `src/doctrine_engine/db/models/doctrine.py`
- `src/doctrine_engine/db/models/features.py`
- `src/doctrine_engine/db/models/learning.py`
- `src/doctrine_engine/db/models/market_data.py`
- `src/doctrine_engine/db/models/signals.py`
- `src/doctrine_engine/db/models/symbols.py`
- `src/doctrine_engine/db/session.py`
- `src/doctrine_engine/db/types.py`
- `src/doctrine_engine/engines/signal_engine.py`
- `src/doctrine_engine/engines/trade_plan_engine.py`
- `src/doctrine_engine/learning/artifact.py`
- `src/doctrine_engine/learning/dataset.py`
- `src/doctrine_engine/learning/features.py`
- `src/doctrine_engine/learning/predict.py`
- `src/doctrine_engine/learning/reporting.py`
- `src/doctrine_engine/learning/schemas.py`
- `src/doctrine_engine/learning/train.py`
- `src/doctrine_engine/learning/validate.py`
- `src/doctrine_engine/product/__init__.py`
- `src/doctrine_engine/product/adapters.py`
- `src/doctrine_engine/product/cli.py`
- `src/doctrine_engine/product/control.py`
- `src/doctrine_engine/product/doctrine_tracking.py`
- `src/doctrine_engine/product/launcher.py`
- `src/doctrine_engine/product/ml_dataset.py`
- `src/doctrine_engine/product/operator_config.py`
- `src/doctrine_engine/product/service.py`
- `src/doctrine_engine/product/state.py`
- `src/doctrine_engine/product/sync.py`
- `src/doctrine_engine/product/web.py`
- `src/doctrine_engine/regime/engine.py`
- `src/doctrine_engine/regime/models.py`
- `src/doctrine_engine/runner/models.py`
- `src/doctrine_engine/runner/pipeline.py`
- `src/doctrine_engine/alerts/models.py`
- `src/doctrine_engine/alerts/telegram_renderer.py`
- `src/doctrine_engine/alerts/workflow.py`

**BATCH 8 — Generated Files (commit: "add generated migration scripts")**
- `alembic/versions/0004_enforce_signal_uniqueness_reconcile_duplicates.py` ← UNTRACKED
- `alembic/versions/0005_outcome_fill_state.py` ← UNTRACKED
- `alembic/versions/0006_candidate_evaluations.py` ← UNTRACKED

**BATCH 9 — Docs (commit: "update documentation")**
- `docs/architecture.md`
- `docs/doctrine_closure_audit_final.md`
- `docs/doctrine_closure_audit_initial.md`
- `docs/doctrine_definitions.md`
- `docs/event_risk_rules.md`
- `docs/final_implementation_verification_final.md`
- `docs/regime_rules.md`
- `docs/signal_contract.md`
- `docs/trade_plan_contract.md`
- `docs/universe_rules.md`

**BATCH 10 — Config/Schema (commit: "update config and schema")**
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/0001_initial_schema.py` ← MODIFIED
- `alembic/versions/0002_signal_timestamp_uniqueness.py` ← MODIFIED
- `pyproject.toml`
- `memory/2026-03-15.md`

**BATCH 11 — Quality/Process (commit: "update quality and operator docs")**
- `Quality.md`
- `Doctrine Operator.vbs`

**BATCH 12 — DO NOT COMMIT**
- `.env.example` — may contain template tokens, review before committing
- `docker-compose.yml` — exists in repo, don't duplicate

### Untracked Files — Classification

**COMMIT (documentation/process — 26 files):**
- `17-4-2026.md`
- `Discord.md` ← check for token/content before committing
- `PAPER_TRADING_READINESS_CHECKLIST.md`
- `alembic/versions/0004_enforce_signal_uniqueness_reconcile_duplicates.py`
- `alembic/versions/0005_outcome_fill_state.py`
- `alembic/versions/0006_candidate_evaluations.py`
- `check_db_tables.py`
- `check_dbs.py`
- `docker-compose.yml` ← check if different from existing
- `docs/ChatGPT-Doctrine project continuation.md`
- `docs/n8n_week1_runbook.md`
- `doctrine.db` ← generated database, don't commit
- `hermes/.env.example`
- `hermes/ACCEPTANCE_CHECKLISTS.md`
- `hermes/CURRENT_STATE.md`
- `hermes/DOCTRINE_CHARTER.md`
- `hermes/DREAMS.md`
- `hermes/IDENTITY_AUTHORITY.md`
- `hermes/INTER_AGENT_PROTOCOL.md`
- `hermes/MANAGEMENT_POLICY.md`
- `hermes/MEMORY.md`
- `hermes/RAW_INTAKE.md`
- `hermes/README.md`
- `hermes/STATE.md`
- `hermes/WORK_QUEUE.md`
- `hermes/WORK_TOPICS.md`

**GENERATED/TEMP (do not commit — 8 files):**
- `operations.db` — generated SQLite
- `lifecycle-after-compact.png`
- `panel-v2-lifecycle-lineage-fix.png`
- `panel-v2-missioncontrol-fix-check.png`
- `panel-v2-operations-8022.png`
- `panel-v2-operations-compact-check.png`
- `panel-v2-operations-fix-check.png`
- `panel-v2-operations-rebuild-8022.png`
- `panel-v2-pipeline-compact-check.png`
- `panel-v2-pipeline-fix-check.png`
- `pipeline-after-compact.png`
- `pipeline-managed-8000.png`
- `tmp-debug.db` — temp debug DB
- `tmp-lifecycle-8022-bottom.png`
- `tmp-lifecycle-8022-new.png`
- `tmp-lifecycle-8022.png`
- `tmp-signals-8022.png`

**ENVIRONMENT-SPECIFIC (do not commit — 3 directories):**
- `frontend/` — environment-specific
- `n8n/` — environment-specific
- `Discord/` — Discord bot files

**UNKNOWN RISK (review before committing — 5 files):**
- `.hermes.md` — unknown content
- `ORCHESTRATOR.md` — unknown content
- `Frontend Skill.md` — unknown content
- `Frontend Skill.md` — check for secrets
- `ORCHESTRATOR.md` — check for secrets

**SHOULD NOT COMMIT (.gitignore these — 2):**
- `.hermes/` — runtime state directory
- `operations.db` — already in generated list

### Recommended Commit Batches

| Batch | Files | Count | Commit Message |
|-------|-------|-------|----------------|
| 1 | OpenClaw config | 3 | "update OpenClaw runtime config and cron" |
| 2 | Docs | 10 | "update architecture and rules documentation" |
| 3 | Config/Schema | 8 | "update config, schema, and pyproject" |
| 4 | Quality/Process | 2 | "update quality docs and operator scripts" |
| 5 | Core engine | 43 | "update core engine models and services" |
| 6 | Tests | 14 | "update test coverage" |
| 7 | hermes/ untracked docs | 16 | "add Hermes operational documentation" |
| 8 | Alembic migrations | 3 | "add new migration scripts" |
| 9 | Ops scripts | 3 | "add operations scripts" |

**TOTAL: 102 files across 9 batches**

**Do NOT commit:** 22 generated/temp files, 3 environment directories, 5 unknown-risk files pending review, 2 .gitignore entries.

---

## 9. DOCTRINE CLOSURE SUMMARY

### What Is Complete

| Item | Status |
|------|--------|
| SOUL.md | ✅ Complete, synced, committed |
| Operating Constitution | ✅ Complete, committed |
| Role Skills Documentation | ✅ Built |
| Health-check.sh | ✅ Built, tested, working |
| drift-check.sh | ✅ Built, 6/6 passing |
| Telegram-only ops | ✅ Discord removed, Prowl removed |
| Execution Gate (A0-A5) | ✅ Defined in SOUL.md + constitution |
| Capital Hierarchy | ✅ Defined in constitution Section 9 |
| P0/P1/P2/P3 Escalation | ✅ Defined in constitution Section 7 |
| 24/7 Cadence | ✅ Defined in constitution Section 5 (not yet automated) |
| Hourly/Daily/Weekly/Monthly cycles | ✅ Defined (automation pending) |

### What Is Enforced

| Item | Status |
|------|--------|
| A0-A5 decision boundaries | ✅ Documented, not programmatically enforced |
| Company todo separation | ✅ Doctrine/Catalyst/Binance todo lists maintained |
| dry_run=true for Binance | ✅ Enforced in profile config |
| Telegram-only | ✅ Enforced (Discord removed) |
| SOUL.md sync check | ✅ drift-check.sh validates |
| Health monitoring | ✅ health-check.sh runs manually |

### What Is Documented But Not Enforced

| Item | Gap |
|------|-----|
| GATEWAY_ALLOW_ALL_USERS=true | Config gap — any Telegram user can DM |
| tirith_fail_open=true | Security gap — unknown security implications |
| No Telegram command auth | No per-command approval model |
| No immutable approval log | All logs editable |
| No systemd autostart | Manual restart only |
| No gateway restart automation | No auto-recovery on crash |
| No rollback procedure | Git is only recovery mechanism |
| pip3 blocked | Hard constraint, not configurable |

### What Remains P0

| Item | Owner | Blocker |
|------|-------|---------|
| GATEWAY_ALLOW_ALL_USERS | Saleh | Needs approval + test |
| tirith_fail_open | Saleh | Needs understanding of Tirith + approval |
| Telegram token exposure | Saleh | Needs BotFather rotation |
| Telegram command auth | Saleh | Needs approval + design |
| Immutable approval log | Me | Needs A4 clarification (new log vs. rewriting) |

### What Remains P1

| Item | Owner | Blocker |
|------|-------|---------|
| Hourly health cron | Me | Can do autonomously |
| Daily MD Brief cron | Me | Can do autonomously |
| drift-check Telegram alert | Me | Can do autonomously |
| Systemd autostart service | Me draft, Saleh approve | Needs approval to enable |
| Rollback procedure doc | Me | Can do autonomously |
| Git commit batches (9 batches) | Me | Needs approval per constitution A4 item 22 |
| pip3 status | Saleh | Clarify if permanent or temporary |

### What Can Be Accepted as Deferred Risk

| Risk | Rationale |
|------|-----------|
| tirith_fail_open=true | Unknown Tirith purpose — investigate before fixing |
| No rollback process | Git provides file-level rollback; documented procedure sufficient |
| No gateway restart automation | Systemd not confirmed working in WSL; health-check alerts are sufficient for now |
| pip3 blocked | You explicitly blocked it — respect the constraint unless you change it |

### What Must Be Fixed Before Catalyst

| Item | Why |
|------|-----|
| GATEWAY_ALLOW_ALL_USERS | P0 security — any Telegram user can access the bot |
| Immutable approval log | Essential for tracking decisions as we move to production |

### What Can Transfer to Catalyst

| Item | Status |
|------|--------|
| Regime classification logic | Already in Catalyst codebase |
| Watchdog kill-switch conditions | Already in Catalyst watchdog.py |
| Signal quality scoring | Already in Catalyst pipeline |
| Backtest framework | In Catalyst/backtrader repo |

### What Can Transfer to Binance

| Item | Status |
|------|--------|
| Risk hierarchy skills | position-sizing, risk-hierarchy, drawdown-recovery skills exist |
| Capital bucket model | Defined in constitution Section 9.2 |
| Drawdown rules | Defined in constitution Section 9.4 |
| Freqtrade integration skill | Exists |
| Binance position tracking skill | Exists |

### Final Recommendation

**CLOSE DOCTRINE WITH ACCEPTED RISKS**

Doctrine is built and operational. The remaining P0 items (GATEWAY_ALLOW_ALL_USERS, tirith_fail_open) require your approval to fix. I can document them, draft the fixes, and test — but cannot apply them without your go-ahead per the constitution.

The critical path forward:
1. You approve GATEWAY_ALLOW_ALL_USERS=false fix → I apply it
2. You clarify tirith — if it's critical, we fix fail_open
3. I implement immutable approval log (A3 scope, I claim)
4. I implement hourly cron for health/drift (A3 scope)
5. We move to Catalyst with P0 items tracked as accepted risks

**Doctrine can close when:**
- All complete items remain complete
- All P0 items are either fixed or formally accepted as deferred risk by you
- Immutable approval log is implemented
- Hourly cron is running
- Catalyst handoff packet is prepared

---

## 10. CATALYST HANDOFF PACKET

### Catalyst Source Path

`/mnt/c/Users/WINDOWS/Documents/CatalystTrader/` (accessible from WSL via `/mnt/c/`)

### The 5 Broken Fixes

| Fix | File | Line | Actual State | Needs From Saleh |
|-----|------|------|-------------|------------------|
| 59 | `src/pipeline.py` | 225 | Bug confirmed: `row[3]` (risk_amount column) used as entry_price fallback in except block. `pos["entry_price"]` is available in scope from `open_positions` lookup. | Confirm: replace `row[3]` with `pos["entry_price"]` |
| 60 | `spec/layer3_v2.md` + `src/database.py` | N/A | Spec drift: `VALID_POSITION_STATUSES` added to `database.py` but `layer3_v2.md` not updated. | Confirm: update layer3_v2.md to document VALID_POSITION_STATUSES |
| 64 | `src/layer0/regime_classifier.py` | 666 | `run_lightweight_l0()` EXISTS — the function IS the fix. Comment says "Fix 59 / Fix 64." Needs verification: is scheduler calling it correctly? | Confirm: is scheduler integration correct, or does scheduler.py need a patch to call it? |
| 65 | `src/scheduler.py` | 33 | Correct nested path used: `state["ml"]["ml_reject_overrides_this_month"]`. The fix IS applied. Needs verification: does `state["ml"]` key always exist before scheduler runs? | Confirm: should scheduler.py initialize `state["ml"]` if it doesn't exist, or is it guaranteed to exist? |
| 10 | `src/watchdog/watchdog.py` + `src/pipeline.py` | watchdog: N/A, pipeline: 1019 | `_send_regime_alert` function EXISTS in `pipeline.py` at line 1019. watchdog.py has NO imports from pipeline.py — it runs as separate process and returns action dicts. The alert routing is at a higher level. | Confirm: does `_send_regime_alert` work as-is, or does watchdog need a new runtime path to call it? |

### Which Fixes Require Saleh Definition

| Fix | Requires Saleh Definition? |
|-----|---------------------------|
| Fix 59 | YES — define the fix (replace row[3] with pos["entry_price"]) |
| Fix 60 | YES — define the spec change (update layer3_v2.md) |
| Fix 64 | YES — confirm scheduler integration is correct or needs a patch |
| Fix 65 | YES — confirm state["ml"] initialization behavior |
| Fix 10 | YES — confirm _send_regime_alert routing works as-is |

**All 5 fixes require your confirmation before I can close CR-002.**

### Which Fixes Can Be Tested Autonomously (after you define them)

| Fix | Can Test After Definition? |
|-----|---------------------------|
| Fix 59 | YES — run backtest, check for risk_amount/entry_price column errors |
| Fix 60 | YES — verify layer3_v2.md contains VALID_POSITION_STATUSES |
| Fix 64 | YES — run scheduler, verify run_lightweight_l0() is called |
| Fix 65 | YES — run scheduler, verify no KeyError on state["ml"] |
| Fix 10 | YES — trigger a regime alert, verify Telegram message received |

### Files Affected

| Fix | Primary File | Backup Files |
|-----|-------------|--------------|
| 59 | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/pipeline.py` | — |
| 60 | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/spec/layer3_v2.md` | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/database.py` |
| 64 | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/layer0/regime_classifier.py` | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/scheduler.py` |
| 65 | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/scheduler.py` | — |
| 10 | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/watchdog/watchdog.py` | `/mnt/c/Users/WINDOWS/Documents/CatalystTrader/src/pipeline.py` |

### Recommended Order of Repair

1. **Fix 59** — lowest risk, clear fix, testable immediately after definition
2. **Fix 65** — test state["ml"] initialization, fix scheduler if needed
3. **Fix 64** — verify scheduler calls run_lightweight_l0(), fix if not
4. **Fix 60** — documentation update, no runtime risk
5. **Fix 10** — last because alert routing is architectural, needs careful confirmation

### Testing Approach

1. Define each fix (you tell me what you want)
2. I draft the patch
3. You approve the patch
4. I apply it
5. Run Catalyst pipeline: `python src/runner.py` or equivalent
6. Verify output — if no errors in 100+ runs, fix is solid
7. Document the fix in catalyst-all.md with verification result

### CR-002 Closure Criteria

CR-002 closes when:
- [ ] Fix 59 applied and pipeline runs 10+ times without `row[3]` column error
- [ ] Fix 60 spec updated and layer3_v2.md verified
- [ ] Fix 64 verified: scheduler calls `run_lightweight_l0()` correctly
- [ ] Fix 65 verified: no KeyError on `state["ml"]` in scheduler runs
- [ ] Fix 10 verified: regime alerts fire and reach Telegram
- [ ] All 5 fixes documented in `catalyst-all.md` with verification evidence
- [ ] Pipeline runs clean on last 10 consecutive executions
- [ ] Regime classification output validated against known market dates
- [ ] Watchdog kill-switch conditions verified still functional

---

## SUMMARY: WHAT I CAN DO WITHOUT ASKING

Per the constitution A3 scope, I claim the following as autonomously executable:

1. **Implement JSONL approval log** — new file, not rewriting existing logs
2. **Add Telegram alert to drift-check.sh** — non-production code fix
3. **Draft systemd service files** — no enable until you approve
4. **Document rollback procedure** — documentation improvement
5. **Draft GATEWAY_ALLOW_ALL_USERS=false fix** — ready for your approval
6. **Prepare all 9 git commit batches** — staged, ready for your approval per A4 item 22
7. **Update catalyst-all.md** with verified fix states from this report

## WHAT REQUIRES YOUR APPROVAL (A4)

1. Apply `GATEWAY_ALLOW_ALL_USERS=false`
2. Rotate Telegram bot token via BotFather
3. Change `tirith_fail_open` setting (defer or apply)
4. Implement command authentication model
5. Enable systemd autostart
6. Git commit the 9 batches (102 files)
7. Immutable approval log (if you consider new log as "rewriting logs")
8. pip3 — clarify if permanent or temporary

## WHAT I NEED FROM CHATGPT (next step)

After this report is reviewed:
1. Which P0 items does Saleh want me to fix now vs. defer?
2. Is the JSONL approval log within my A3 scope or does it need approval?
3. Should I proceed with git commit batching while we work on P0 items?
