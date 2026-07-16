# Claude Code — Hook Setup

This connects Claude Code to memward using its native hook system. Capture is **automatic and deterministic** — it fires at the end of every turn regardless of what the model does, no tool call required.

## How it works — three reliability layers

| Layer | Hook | When it fires | What it does |
|---|---|---|---|
| 1 (primary) | `Stop` | End of every turn | Reads new transcript lines since last checkpoint, POSTs to `/ingest` |
| 2 (reconciliation) | `SessionStart` | Every time Claude Code opens | Catches any transcripts the Stop hook missed (abrupt kills, crashes) |
| 3 (last resort) | launchd / cron | Every few minutes, always | Filesystem sweep independent of any hook firing |

Install all three for full reliability.

---

## Prerequisites

- memward core API running on `http://127.0.0.1:8000`
- Python 3.11+ available at the path used by the hook scripts
- `uv sync` already run from the repo root

---

## Step 1 — Make hook scripts executable

```bash
chmod +x /absolute/path/to/memward/connectors/claude_code/stop_hook.py
chmod +x /absolute/path/to/memward/connectors/claude_code/session_start_hook.py
```

---

## Step 2 — Register hooks in Claude Code settings

Open (or create) `~/.claude/settings.json` and add the `hooks` section below. Replace `/absolute/path/to/memward` with the real path where you cloned the repo.

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "/absolute/path/to/memward/connectors/claude_code/stop_hook.py"
      }
    ],
    "SessionStart": [
      {
        "type": "command",
        "command": "/absolute/path/to/memward/connectors/claude_code/session_start_hook.py"
      }
    ]
  }
}
```

If you already have other hooks configured, add the memward entries inside the existing `"Stop"` and `"SessionStart"` arrays — do not replace the whole file.

**Example on macOS** (if you cloned to `~/projects/memward`):

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "/Users/yourname/projects/memward/connectors/claude_code/stop_hook.py"
      }
    ],
    "SessionStart": [
      {
        "type": "command",
        "command": "/Users/yourname/projects/memward/connectors/claude_code/session_start_hook.py"
      }
    ]
  }
}
```

---

## Step 3 — Install the filesystem sweep (Layer 3, macOS)

This runs every 5 minutes in the background, independent of any Claude Code event, as a last-resort catch for hard process kills.

Create a launchd plist at `~/Library/LaunchAgents/com.memward.sweep.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.memward.sweep</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/absolute/path/to/memward/connectors/claude_code/session_start_hook.py</string>
  </array>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>/tmp/memward-sweep.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/memward-sweep.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.memward.sweep.plist
```

To unload later:

```bash
launchctl unload ~/Library/LaunchAgents/com.memward.sweep.plist
```

**Linux / cron alternative:**

```bash
crontab -e
# Add this line:
*/5 * * * * /usr/bin/python3 /absolute/path/to/memward/connectors/claude_code/session_start_hook.py
```

---

## Step 4 — Verify

1. Start a Claude Code session and have a short conversation
2. At the end of the turn, the Stop hook fires automatically
3. Check the curation UI at [http://localhost:5173](http://localhost:5173) — you should see a new `pending_review` memory appear within seconds

You can also check the ingest endpoint directly:

```bash
curl 'http://127.0.0.1:8000/curation/memories?status_filter=pending_review&limit=5'
```

---

## Configuration (optional env vars)

The hook scripts read these environment variables if set. Defaults work for local development.

| Variable | Default | Description |
|---|---|---|
| `MEMWARD_INGEST_URL` | `http://127.0.0.1:8000/ingest` | Core API ingest endpoint |
| `MEMWARD_SEARCH_URL` | `http://127.0.0.1:8000/search` | Core API search endpoint |
| `MEMWARD_WORKSPACE_ID` | `default-workspace` | Workspace to write memories into |
| `MEMWARD_CHECKPOINT_DIR` | `~/.memward/checkpoints/` | Where per-session checkpoints are stored; checkpoints advance only after durable ingest acceptance |
| `MEMWARD_INGEST_TIMEOUT` | `5` | Seconds before ingest HTTP call times out |
| `MEMWARD_INJECT_LIMIT` | `20` | Max approved memories injected at SessionStart |

---

## Troubleshooting

**No memories appearing after a session**
- Confirm the core API is running: `curl http://127.0.0.1:8000/health`
- Check the hook script is executable: `ls -la connectors/claude_code/stop_hook.py`
- Run the hook manually to see errors: `echo '{"session_id":"test","transcript_path":"/nonexistent","hook_event_name":"Stop","cwd":"/tmp"}' | python3 /path/to/stop_hook.py`

**`Permission denied` when hook fires**
- Re-run `chmod +x` on both hook scripts

**Hook fires but processor never writes a memory**
- Confirm the processor is running on port 8010: `curl http://127.0.0.1:8010/health`
- Check `PROCESSOR_API_URL` in your `.env` matches port 8010
