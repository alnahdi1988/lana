#!/bin/bash
# drift-check.sh — WSL adaptation of drift-check.ps1
# Checks OpenClaw runtime config alignment with Doctrine repo
# Run from: ~/hermes/doctrine/repo/

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/mnt/d/Doctrine/structure-doctrine-engine}"
SOUL_LIVE="$HOME/.hermes/SOUL.md"
SOUL_SEED="$REPO_ROOT/hermes/HERMES_SOUL.md"
PROFILE_DIR="$HOME/.hermes/profiles/doctrine"
RUNTIME_JSON="$REPO_ROOT/.openclaw/openclaw.json"
RENDER_SCRIPT="$REPO_ROOT/.openclaw/render-config.ps1"

# Telegram alerting (failures only)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_ALERT_CHAT_ID:-8569633077}"
ALERT_ON_FAIL="${DRIFT_ALERT_ON_FAIL:-true}"

PASS=0
FAIL=0
FAIL_REASONS=()

function ok {
    echo "[OK] $1"
    PASS=$((PASS + 1))
}

function fail {
    echo "[FAIL] $1"
    FAIL=$((FAIL + 1))
    FAIL_REASONS+=("$1")
}

function warn {
    echo "[WARN] $1"
}

function alert_telegram {
    local msg="$1"
    if [[ "$ALERT_ON_FAIL" != "true" ]] || [[ -z "$TELEGRAM_BOT_TOKEN" ]]; then
        return 0
    fi
    curl -s --max-time 10 \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=⚠️ Doctrine Drift: $msg" \
        -d "parse_mode=HTML" > /dev/null 2>&1
    local curl_exit=$?
    if [[ $curl_exit -ne 0 ]]; then
        echo "[WARN] Telegram alert delivery failed (curl exit $curl_exit)" >&2
    fi
}

echo "=== Doctrine OpenClaw Drift Check ==="
echo "Repo: $REPO_ROOT"
echo ""

# 1. Hermes doctrine profile exists
if [[ -d "$PROFILE_DIR" ]]; then
    ok "Hermes doctrine profile exists: $PROFILE_DIR"
else
    fail "Hermes doctrine profile missing: $PROFILE_DIR"
fi

# 2. SOUL.md exists and matches seed
if [[ -f "$SOUL_LIVE" ]]; then
    if [[ -f "$SOUL_SEED" ]]; then
        if diff -q "$SOUL_LIVE" "$SOUL_SEED" > /dev/null 2>&1; then
            ok "SOUL.md live matches repo seed"
        else
            fail "SOUL.md live differs from hermes/HERMES_SOUL.md"
        fi
    else
        warn "hermes/HERMES_SOUL.md not found in repo"
    fi
else
    fail "~/.hermes/SOUL.md not found"
fi

# 3. Telegram transport present in openclaw.json
if [[ -f "$RUNTIME_JSON" ]]; then
    if grep -q '"telegram"' "$RUNTIME_JSON"; then
        ok "Telegram transport present in openclaw.json"
    else
        fail "Telegram transport missing from openclaw.json"
    fi

    # Telegram binding
    if python3 -c "
import json, sys
with open('$RUNTIME_JSON', 'rb') as f:
    raw = f.read()
if raw.startswith(b'\xef\xbb\xbf'):
    raw = raw[3:]
cfg = json.loads(raw)
for b in cfg.get('bindings', []):
    if b.get('match', {}).get('channel') == 'telegram':
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        ok "aria-chat -> Telegram binding exists"
    else
        fail "aria-chat Telegram binding missing"
    fi
else
    fail "openclaw.json not found: $RUNTIME_JSON"
fi

# 4. No __REPO_ROOT__ tokens in generated config
if [[ -f "$RUNTIME_JSON" ]]; then
    if grep -q '__REPO_ROOT__' "$RUNTIME_JSON"; then
        fail "__REPO_ROOT__ tokens remain in openclaw.json"
    else
        ok "No __REPO_ROOT__ tokens in generated config"
    fi
fi

# 5. render-config.ps1 exists
if [[ -f "$RENDER_SCRIPT" ]]; then
    ok "render-config.ps1 present"
else
    fail "render-config.ps1 not found: $RENDER_SCRIPT"
fi

echo ""
echo "=== DRIFT CHECK: $PASS passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
    # Send Telegram alert with redacted summary
    fail_summary=$(printf '%s; ' "${FAIL_REASONS[@]}" 2>/dev/null || echo "Unknown")
    alert_telegram "Drift check FAILED ($FAIL checks). Issues: ${fail_summary%; }"
    alert_telegram "Run: drift-check.sh for full output. Review ~/.hermes/doctrine/repo/"

    # Log to approval log
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    LOG_JSON="{\"timestamp\":\"${TS}\",\"company\":\"Doctrine\",\"decision_category\":\"drift_check\",\"requested_action\":\"runtime_config_drift_detection\",\"approval_status\":\"fail\",\"approver\":\"hermes_drift_check\",\"source_command\":\"drift-check.sh\",\"affected_file_config\":\"openclaw.json, SOUL.md\",\"before_state\":\"${FAIL} checks failed\",\"after_state\":\"telegram_alert_sent\",\"rollback_reference\":\"review_fail_reasons\",\"commit_hash\":\"\",\"incident_reference\":\"drift_${FAIL}\"}"
    echo "${LOG_JSON}" >> /home/saleh/.hermes/doctrine/approval-log.jsonl 2>/dev/null || true

    exit 1
else
    echo "All checks passed."
    exit 0
fi
