# Claude Desktop — MCP Setup

This connects Claude Desktop to memward so it can call `save_memory` and `search_memory` during your conversations.

## Prerequisites

- memward core API running on `http://127.0.0.1:8000`
- `uv` installed and `uv sync` already run from the repo root

## How it works

A small stdio MCP bridge (`connectors/claude_desktop/mcp_server.py`) runs as a local process. Claude Desktop launches it automatically and communicates over stdin/stdout. The bridge forwards all tool calls to the running core API.

---

## Step 1 — Find your Claude Desktop config file

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

If the file does not exist yet, create it.

---

## Step 2 — Register the MCP server

Add the following to `claude_desktop_config.json`. Replace `/absolute/path/to/memward` with the actual path where you cloned the repo.

```json
{
  "mcpServers": {
    "memward": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/memward",
        "python",
        "/absolute/path/to/memward/connectors/claude_desktop/mcp_server.py"
      ]
    }
  }
}
```

**Example on macOS** (if you cloned to `~/projects/memward`):

```json
{
  "mcpServers": {
    "memward": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/yourname/projects/memward",
        "python",
        "/Users/yourname/projects/memward/connectors/claude_desktop/mcp_server.py"
      ]
    }
  }
}
```

If you already have other MCP servers configured, add the `"memward"` entry inside the existing `"mcpServers"` object — do not replace the whole file.

---

## Step 3 — Restart Claude Desktop

Quit and reopen Claude Desktop. It will launch the bridge process automatically on startup.

---

## Step 4 — Verify

In a new Claude Desktop conversation, ask:

> "Search my memory for anything about Python"

Claude Desktop should call `search_memory` (you'll see the tool call appear in the UI). If the core API is running, it will return results (or an empty list if no approved memories exist yet).

To save a memory manually:

> "Save to memory: I prefer Python over JavaScript for backend work"

---

## Troubleshooting

**Tool calls don't appear**
- Confirm the core API is running: `curl http://127.0.0.1:8000/health` should return `{"status":"ok"}`
- Check the path in `claude_desktop_config.json` is absolute and correct
- Restart Claude Desktop after any config change

**`uv: command not found`**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Or use the full path to uv (find it with `which uv`) in the `"command"` field

**MCP server crashes on launch**
- Run the bridge manually to see the error: `uv run --project /path/to/memward python /path/to/memward/connectors/claude_desktop/mcp_server.py`

---

## How capture works (best-effort)

Claude Desktop capture depends on the model choosing to call `save_memory` during a conversation. It is not automatic. To make it reliable:

- At the end of important sessions, explicitly ask: *"Save a summary of this conversation to memory"*
- The model will call `save_memory` — the memory lands as `pending_review` and appears in the curation UI for your approval
