#!/usr/bin/env python3
"""
Claude Code SessionStart hook — reconciliation path.

Fires whenever Claude Code opens (startup, resume, clear, compact).
Scans ~/.claude/projects/ for transcript files that were modified after
the last known checkpoint and re-ingest any lines that the Stop hook
missed (e.g. from abrupt process kills).

Per AGENTS.md, this is the SECOND reliability layer behind the Stop hook.
The third layer (filesystem sweep) is a launchd/cron job — see docs/.

Payload received from Claude Code via stdin (JSON):
  {
    "session_id": "...",
    "hook_event_name": "SessionStart",
    "source": "startup" | "resume" | "clear" | "compact"
  }

Setup:
  Add this to ~/.claude/settings.json under hooks.SessionStart:
    {
      "type": "command",
      "command": "/path/to/connectors/claude_code/session_start_hook.py"
    }
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

# ── Config (override via env vars) ──────────────────────────────────────────
INGEST_URL = os.environ.get("MEMWARD_INGEST_URL", "http://127.0.0.1:8000/ingest")
SEARCH_URL = os.environ.get("MEMWARD_SEARCH_URL", "http://127.0.0.1:8000/search")
WORKSPACE_ID = os.environ.get("MEMWARD_WORKSPACE_ID", "default-workspace")
CHECKPOINT_DIR = Path(os.environ.get("MEMWARD_CHECKPOINT_DIR", Path.home() / ".memward" / "checkpoints"))
CLAUDE_PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude" / "projects"))
TIMEOUT_SECONDS = int(os.environ.get("MEMWARD_INGEST_TIMEOUT", "5"))
MEMORY_INJECT_LIMIT = int(os.environ.get("MEMWARD_INJECT_LIMIT", "20"))


def checkpoint_path(session_id: str) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"{session_id}.json"


def load_checkpoint(session_id: str) -> int:
    path = checkpoint_path(session_id)
    if path.exists():
        try:
            return json.loads(path.read_text()).get("lines_ingested", 0)
        except Exception:
            return 0
    return 0


def save_checkpoint(session_id: str, lines_ingested: int) -> None:
    checkpoint_path(session_id).write_text(json.dumps({"lines_ingested": lines_ingested}))


def read_new_lines(transcript_path: Path, from_line: int) -> tuple[list[dict], int]:
    lines = transcript_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for raw in lines[from_line:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            new_lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return new_lines, len(lines)


def extract_content(turns: list[dict]) -> str:
    parts = []
    for turn in turns:
        turn_type = turn.get("type", "")
        if turn_type not in ("user", "assistant"):
            continue
        msg = turn.get("message", {})
        role = msg.get("role", turn_type)
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = " ".join(text_parts)
        if content and isinstance(content, str) and content.strip():
            parts.append(f"[{role}]: {content.strip()}")
    return "\n".join(parts)


def post_to_ingest(session_id: str, content: str, source_event: str) -> bool:
    payload = json.dumps({
        "source": "claude_code",
        "workspace_id": WORKSPACE_ID,
        "content": content,
        "provenance": {
            "session_id": session_id,
            "hook": "SessionStart",
            "reconciliation_trigger": source_event,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        INGEST_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status == 202
    except Exception:
        return False


def reconcile_missed_sessions(current_session_id: str, source_event: str) -> None:
    """
    Scan all transcript files in ~/.claude/projects/ and re-ingest
    any lines that the Stop hook didn't process.
    """
    if not CLAUDE_PROJECTS_DIR.exists():
        return

    for transcript_file in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        # Derive a stable session_id from the file path
        session_id = transcript_file.stem
        if session_id == current_session_id:
            continue  # Current session is handled by the Stop hook going forward

        last_line = load_checkpoint(session_id)
        try:
            new_turns, total_lines = read_new_lines(transcript_file, last_line)
        except Exception:
            continue

        if not new_turns:
            continue

        content = extract_content(new_turns)
        if not content.strip():
            save_checkpoint(session_id, total_lines)
            continue

        success = post_to_ingest(session_id, content, source_event)
        if success:
            save_checkpoint(session_id, total_lines)


def fetch_and_inject_memories() -> None:
    """
    Fetch all approved memories from the memward server and append them
    to the model's prompt context via Claude Code's hook JSON output.

    Writes {"context": "..."} to stdout — Claude Code injects this into
    the model's context silently, without showing it as a user message.

    Silently skips if the server is not running — memory is best-effort.
    """
    params = urllib.parse.urlencode({
        "limit": MEMORY_INJECT_LIMIT,
        "workspace_id": WORKSPACE_ID,
    })
    url = f"{SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return

    results = data.get("results", [])
    if not results:
        return

    lines = ["Approved memories from previous sessions:\n"]
    for r in results:
        category = r.get("category", "general")
        source = r.get("source", "unknown")
        content = r.get("content", "").strip()
        if content:
            lines.append(f"[{category} / {source}] {content}")

    context_text = "\n".join(lines)
    sys.stdout.write(json.dumps({"context": context_text}))
    sys.stdout.flush()


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    current_session_id = event.get("session_id", "unknown")
    source_event = event.get("source", "startup")

    reconcile_missed_sessions(current_session_id, source_event)
    fetch_and_inject_memories()


if __name__ == "__main__":
    main()
