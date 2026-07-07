#!/usr/bin/env python3
"""
Claude Code Stop hook — primary capture path.

Fires at the end of every turn. Reads new lines from the session
transcript since the last checkpoint and POSTs them to the memward
ingest endpoint.

Per AGENTS.md:
- This hook is the PRIMARY capture mechanism for Claude Code.
- Do NOT replace this with a save_memory MCP tool call — that is the
  Copilot/Claude Desktop fallback only.

Payload received from Claude Code via stdin (JSON):
  {
    "session_id": "...",
    "transcript_path": "/path/to/transcript.jsonl",
    "hook_event_name": "Stop",
    "cwd": "/current/working/dir"
  }

Setup:
  Add this to ~/.claude/settings.json under hooks.Stop:
    {
      "type": "command",
      "command": "/path/to/connectors/claude_code/stop_hook.py"
    }
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

# ── Config (override via env vars) ──────────────────────────────────────────
INGEST_URL = os.environ.get("MEMWARD_INGEST_URL", "http://127.0.0.1:8000/ingest")
WORKSPACE_ID = os.environ.get("MEMWARD_WORKSPACE_ID", "default-workspace")
CHECKPOINT_DIR = Path(os.environ.get("MEMWARD_CHECKPOINT_DIR", Path.home() / ".memward" / "checkpoints"))
TIMEOUT_SECONDS = int(os.environ.get("MEMWARD_INGEST_TIMEOUT", "5"))


def checkpoint_path(session_id: str) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"{session_id}.json"


def load_checkpoint(session_id: str) -> int:
    """Return the last ingested line count for this session (0 = never ingested)."""
    path = checkpoint_path(session_id)
    if path.exists():
        try:
            return json.loads(path.read_text()).get("lines_ingested", 0)
        except Exception:
            return 0
    return 0


def save_checkpoint(session_id: str, lines_ingested: int) -> None:
    checkpoint_path(session_id).write_text(json.dumps({"lines_ingested": lines_ingested}))


def read_new_lines(transcript_path: str, from_line: int) -> tuple[list[dict], int]:
    """
    Read all JSONL lines from the transcript file starting at from_line.
    Returns (new_lines, total_line_count).
    """
    path = Path(transcript_path)
    if not path.exists():
        return [], from_line

    lines = path.read_text(encoding="utf-8").splitlines()
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
    """
    Extract human-readable text from JSONL transcript turns.

    Real Claude Code JSONL format:
      { "type": "user" | "assistant", "message": { "role": "...", "content": ... } }
    Content may be a plain string or a list of content blocks.
    """
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
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    for inner in block.get("content", []):
                        if isinstance(inner, dict) and inner.get("type") == "text":
                            text_parts.append(inner.get("text", ""))
            content = " ".join(text_parts)
        if content and isinstance(content, str) and content.strip():
            parts.append(f"[{role}]: {content.strip()}")
    return "\n".join(parts)


def post_to_ingest(session_id: str, cwd: str, content: str) -> bool:
    """
    POST raw content to the memward ingest endpoint.
    Returns True on success (202), False otherwise.
    Non-blocking: any exception is swallowed so the hook never breaks Claude Code.
    """
    payload = json.dumps({
        "source": "claude_code",
        "workspace_id": WORKSPACE_ID,
        "content": content,
        "provenance": {
            "session_id": session_id,
            "cwd": cwd,
            "hook": "Stop",
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


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = event.get("session_id", "unknown")
    transcript_path = event.get("transcript_path", "")
    cwd = event.get("cwd", "")

    if not transcript_path:
        sys.exit(0)

    last_line = load_checkpoint(session_id)
    new_turns, total_lines = read_new_lines(transcript_path, last_line)

    if not new_turns:
        sys.exit(0)

    content = extract_content(new_turns)
    if not content.strip():
        save_checkpoint(session_id, total_lines)
        sys.exit(0)

    success = post_to_ingest(session_id, cwd, content)

    # Always advance checkpoint even on ingest failure so we don't
    # re-send the same lines on the next turn. The SessionStart
    # reconciliation hook handles genuine missed sessions.
    if success or True:
        save_checkpoint(session_id, total_lines)


if __name__ == "__main__":
    main()
