#!/usr/bin/env python3
"""
OpenCode memory injection — sync approved memories to an instructions file.

OpenCode has no hooks. Memory injection works via the `instructions` key in
opencode.json, which points to markdown files loaded into every session.

This script fetches all approved memories from the memward API and writes
them to a markdown file that opencode.json should reference via `instructions`.

Run this manually or via a launchd/cron job to keep the file fresh.

Per AGENTS.md:
- OpenCode capture is best-effort (model calls save_memory MCP tool).
- There is no hook-driven automatic capture equivalent to Claude Code.
- Injection is via the `instructions` config key, not a hook.

Usage:
    python3 connectors/opencode/sync_memories.py

    # Or with custom paths/URLs:
    MEMWARD_SEARCH_URL=http://127.0.0.1:8000/search \\
    MEMWARD_OUTPUT_FILE=~/.config/opencode/memward-memories.md \\
    python3 connectors/opencode/sync_memories.py

Setup (add to opencode.json):
    {
      "$schema": "https://opencode.ai/config.json",
      "instructions": ["~/.config/opencode/memward-memories.md"]
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
OUTPUT_FILE = Path(
    os.environ.get(
        "MEMWARD_OUTPUT_FILE",
        Path.home() / ".config" / "opencode" / "memward-memories.md",
    )
).expanduser()


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
    except Exception as e:
        print(f"[memward] Failed to fetch memories: {e}", file=sys.stderr)
        return []


def write_instructions_file(memories: list[dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not memories:
        # Write an empty file so opencode.json reference doesn't break
        OUTPUT_FILE.write_text("", encoding="utf-8")
        print(f"[memward] No approved memories — cleared {OUTPUT_FILE}")
        return

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

    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[memward] Wrote {len(memories)} memories to {OUTPUT_FILE}")


def main() -> None:
    memories = fetch_approved_memories()
    write_instructions_file(memories)


if __name__ == "__main__":
    main()
