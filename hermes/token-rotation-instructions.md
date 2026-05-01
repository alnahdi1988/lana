# Telegram Token Rotation — Instructions for Saleh
# Status: DRAFT — Do not rotate until new token is provided

---

## IMPORTANT: Do NOT print the current token here

The current token is stored in `~/.hermes/.env` and must never appear in plain text
in any documentation, log, or chat message.

---

## Why Rotate?

The current token prefix is `834475...`. If this token has been exposed anywhere
(shared in a chat, committed to a repo, logged somewhere), it must be rotated
immediately to prevent unauthorized access.

---

## Step-by-Step Rotation via BotFather

### Step 1: Get a New Token
1. Open Telegram and search for **@BotFather**
2. Send `/mybots`
3. Select **@HermesAgentCEOBot** (or whichever bot token you are rotating)
4. Tap **API Token**
5. Tap **Revoke** — this invalidates the current token
6. BotFather will show you a **new token** in format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ`
7. Copy the new token NOW — it will only be shown once

### Step 2: Where to Place the New Token
The new token goes in `~/.hermes/.env` on **line 11**:

```
TELEGRAM_BOT_TOKEN=<NEW_TOKEN_HERE>
```

Example (DO NOT USE THIS):
```
TELEGRAM_BOT_TOKEN=834475...Mk0I
```

To update:
```bash
# Edit the .env file
nano ~/.hermes/.env
# Find line 11, replace the token value
# Save and exit
```

### Step 3: Verify the New Token Works (without exposing it)
After updating .env, verify the bot connects correctly:

```bash
# Test bot connectivity — the token is in the env, not printed
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
```

Expected output: `{"ok":true,"result":{"id":...,...}}`

Then restart Hermes:
```bash
HERMES_PID=$(pgrep -f "hermes.*resume" | head -1)
kill $HERMES_PID
sleep 2
nohup /home/saleh/.hermes/hermes-agent/venv/bin/python3 /home/saleh/.local/bin/hermes --resume latest > /home/saleh/.hermes/logs/hermes-agent.log 2>&1 &
```

### Step 4: Test from Telegram
- Send a DM to the bot from your Telegram account
- Confirm it responds

---

## Old Token Exposure Documentation

After rotation, document where the old token appeared:

```bash
# Search for old token in all logs (prefix only — never the full token)
grep -r "834475" ~/.hermes/logs/ 2>/dev/null
grep -r "834475" /mnt/d/Doctrine/structure-doctrine-engine/ 2>/dev/null | grep -v ".git/"

# If found: archive or redact those log files
# Do NOT delete logs — archive them
```

If old token was committed to any git repo:
```bash
cd /mnt/d/Doctrine/structure-doctrine-engine
git log --all --source --remotes --grep="834475" --oneline
# Or search for the token in git history
git log --all -p | grep "834475" | head -20
```

If found in git history: that commit must be amended or reverted.

---

## Files / Logs That Need Review After Rotation

| File / Location | Risk | Action |
|---|---|---|
| `~/.hermes/logs/gateway.log` | Possible token in startup | Review and redact if found |
| `~/.hermes/logs/agent.log` | Possible token in startup | Review and redact if found |
| `/mnt/d/Doctrine/structure-doctrine-engine/` | Possible token in docs/notes | Search and remove if found |
| Any `.md` file in repo | Token in notes/docs | Remove and amend git history |
| Git commit messages | Token in commit messages | `git filter-branch` or BFG Repo-Cleaner |

---

## If New Token Doesn't Work

1. Verify token format: must be `numbers:letters` (e.g. `834475:Mk0I...`)
2. Verify no spaces or newlines in .env value
3. Verify bot hasn't been deleted or banned
4. Try `curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"` again
5. Check Hermes logs: `tail -50 ~/.hermes/logs/hermes-agent.log`

---

## Token Format Reference

Current token format: `834475...:Mk0I...` (numeric ID : auth string)
New token will follow same format with different numbers/characters.

The token is case-sensitive.
