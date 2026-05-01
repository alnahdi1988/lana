# Tirith Fail-Open Decision — Final Options
# Status: AWAITING USER DECISION — Do not apply any change yet

---

## What is Tirith?

Tirith is an ELF binary at `~/.hermes/bin/tirith` — purpose verified as a token
wrapper/interceptor for gateway authentication. It wraps API calls and enforces
token validation before reaching the gateway. The binary is stripped (no symbols)
and its exact behavior cannot be reverse-engineered from strings output.

---

## What is tirith_fail_open?

A configuration flag that determines what happens if Tirith fails:
- `tirith_fail_open=true`: If Tirith crashes or fails, gateway allows all users (permissive)
- `tirith_fail_open=false`: If Tirith crashes or fails, gateway blocks all users (restrictive)

---

## Current State

`tirith_fail_open` setting **not found** in `.env`, `config.yaml`, or any config file.
The binary exists and runs. The setting location is unknown.
Binary default behavior is **assumed permissive** (fail-open) based on the
`GATEWAY_ALLOW_ALL_USERS=true` security posture.

---

## Option A: Apply tirith_fail_open=false Now

**What it does:** Forces restrictive fail behavior — if Tirith fails, all users are blocked.

**Operational impact:**
- If Tirith has any bug or crash, bot becomes completely inaccessible to all users
- No graceful degradation — hard lockout on failure
- Requires manual intervention to restore access

**Security impact:**
- Eliminates the fail-open attack surface
- An attacker cannot exploit Tirith crash to bypass authentication

**Lockout risk:**
- HIGH — if Tirith fails for any reason, all users including Saleh are locked out
- Recovery requires WSL access to remove tirith from PATH or disable the setting

**Rollback method:**
```bash
# Remove the setting — reverts to binary default (fail-open)
sed -i '/tirith_fail_open/d' ~/.hermes/.env
# Restart Hermes
```

**Recommendation:** NOT RECOMMENDED without knowing why Tirith fails and how often.
High operational risk for uncertain security benefit.

---

## Option B: Defer with Explicit Risk Acceptance

**What it does:** Document that fail-open is an accepted operational risk.
Do not change the setting until Tirith behavior is better understood.

**Operational impact:**
- No change to current behavior
- Risk is documented and accepted by owner

**Security impact:**
- Fail-open remains — if Tirith fails, all users allowed
- Risk acknowledged in risk register

**Lockout risk:**
- NONE — current behavior preserved

**Rollback method:**
- N/A — no change applied

**Recommendation:** RECOMMENDED if the current security posture is acceptable
given the controls already in place (allowed_chat_ids, allowed_user_ids).
Low operational risk.

---

## Option C: Test Tirith Behavior First, Then Decide

**What it does:** Run a controlled empirical test to determine:
1. Does Tirith actually fail?
2. What happens when it fails?
3. How often does it fail?

**Steps:**
1. Set up monitoring to capture Tirith exit codes
2. Run for 1 week with logging: `strace -f tirith ...` (if performance allows)
3. Review failure frequency and impact
4. Make decision based on actual data

**Operational impact:**
- No production change during test period
- May slightly degrade performance with strace

**Security impact:**
- Test data informs the decision — no new risk introduced

**Lockout risk:**
- LOW — monitoring only, no changes to fail behavior

**Rollback method:**
- Stop the strace/monitoring
- No config change needed

**Recommendation:** RECOMMENDED as the right approach for a production system.
Data before decision.

---

## Stark's Recommendation

**Option C — Test First, Then Decide**

Rationale:
- We don't fully understand Tirith's failure modes
- Option A (apply false now) creates high lockout risk without data
- Option B (defer) is acceptable but leaves an uncharacterized risk
- Option C builds the evidence base for the right long-term decision
- This aligns with the standard: "verify before building"

The binary exists but its failure behavior is uncharacterized. Test it.

---

## What I Need to Implement Option C

1. A test period (1 week recommended)
2. A way to observe Tirith exit codes — possibly via a wrapper script
3. Saleh approval to run the test

Once test data is available, I will present findings with a final recommendation.
