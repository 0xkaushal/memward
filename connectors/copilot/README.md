# Copilot Connector

Capture mechanism for **GitHub Copilot (VS Code agent mode)** and **Claude Desktop**.

Per `AGENTS.md`, this is a **best-effort** connector — capture only happens when the
model decides to emit a `save_memory` tool call, or the user explicitly asks for it.
There is no background hook equivalent to the Claude Code `Stop` hook.

## How it works

1. The memward FastAPI server exposes MCP tool routes at:
   - `POST /mcp/save_memory`
   - `GET  /mcp/search_memory`

2. `.vscode/mcp.json` (repo root) registers the server with VS Code so Copilot
   agent mode discovers the tools automatically when the server is running.

3. `.github/copilot-instructions.md` instructs the model on *when* to call each
   tool — on startup (search), when something noteworthy happens (save), and on
   explicit user request.

## Running the server

```bash
# From repo root
uv run uvicorn core.main:app --app-dir src --host 127.0.0.1 --port 8000
```

The server must be running for VS Code to discover the MCP tools.

## Config files

| File | Purpose |
|------|---------|
| `.vscode/mcp.json` | Registers the HTTP MCP server with VS Code |
| `.github/copilot-instructions.md` | Instructs Copilot when/how to call the tools |

## Limitations

- Only works in VS Code **agent mode** — not inline autocomplete or other Copilot surfaces.
- If the server is not running, tool calls are silently skipped (by design — do not block on memory ops).
- Memories land as `pending_review` and only feed back into `search_memory` once approved.
