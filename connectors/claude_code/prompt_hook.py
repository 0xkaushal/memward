#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook — inject fresh approved memories on every turn.

Fires before every prompt is sent to the model. Fetches all approved memories
from the memward API and injects them as additionalContext so the model always
has the latest memories — even if they were approved mid-session.

This solves the SessionStart limitation where memories approved after session
start were invisible until the next session.

Per AGENTS.md:
- This is a reliability improvement on top of the SessionStart hook.
- SessionStart still writes MEMORY.md for session-level context.
- This hook ensures mid-session approvals are immediately available.

Payload received from Claude Code via stdin (JSON):
  {
    "session_id": "...",
    "transcript_path": "/path/to/transcript.jsonl",
    "hook_event_name": "UserPromptSubmit",
    "cwd": "/current/working/dir",
    "prompt": "the user's prompt text"
  }

Output to stdout (JSON):
  {
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": "# Memories from previous sessions\\n- ..."
    }
  }

Setup:
  Add this to ~/.claude/settings.json under hooks.UserPromptSubmit:
    {
      "type": "command",
      "command": "/path/to/connectors/claude_code/prompt_hook.py",
      "timeout": 5
    }
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SEARCH_URL = os.environ.get("MEMWARD_SEARCH_URL", "http://127.0.0.1:8000/search")
WORKSPACE_ID = os.environ.get("MEMWARD_WORKSPACE_ID", "default-workspace")
INJECT_LIMIT = int(os.environ.get("MEMWARD_INJECT_LIMIT", "20"))
TIMEOUT_SECONDS = int(os.environ.get("MEMWARD_INGEST_TIMEOUT", "5"))


def fetch_approved_memories() -> list[dict]:
    params = urllib.parse.urlencode({
        "limit": INJECT_LIMIT,
        "workspace_id": WORKSPACE_ID,
    })
    url = f"{SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except Exception:
        return []


def build_context(memories: list[dict]) -> str | None:
    if not memories:
        return None
    lines = [
        "# Context from previous sessions",
        "",
        "The following facts were saved from previous sessions and approved for use.",
        "Treat them as ground truth unless the user says otherwise.",
        "",
    ]
    for r in memories:
        content = r.get("content", "").strip()
        if content:
            lines.append(f"- {content}")
    return "\n".join(lines)


def main() -> None:
    # Read stdin but don't need to parse it — we inject memories unconditionally
    sys.stdin.read()

    memories = fetch_approved_memories()
    context = build_context(memories)

    if not context:
        # No memories — exit cleanly with no output, hook is a no-op
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
