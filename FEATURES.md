# Features

All features currently implemented in memward v0.1.0.

---

## Core API (`src/core/`)

### Ingestion — `POST /ingest`
- Accepts raw memory content from any source (`claude_code`, `copilot`, `claude_desktop`, `internal_chatbot_x`)
- Validates source field; returns HTTP 400 on invalid input
- Writes a `RawSession` row immediately (durable record)
- Dispatches async HTTP POST to the processor app (fire-and-forget, 3s timeout)
- Returns `202 Accepted` with `session_id` and `processor_dispatch` status regardless of processor outcome

### Search — `GET /search`
- Returns approved memories only — `pending_review` and `archived` never appear
- Filters strictly by `workspace_id`
- Keyword search (`ILIKE`) on memory content when a query is provided
- Returns most-recent approved memories when no query is provided (used by SessionStart hook to inject context)
- Configurable result limit (1–25, default 5)

### Health — `GET /health`
- Liveness check, returns `{"status": "ok"}`

### Root — `GET /`
- Service identity response

---

## Curation API (`src/core/routes/curation.py`)

The backend for the human review gate — the core product differentiator.

### List memories — `GET /curation/memories`
- Returns all memories regardless of status (pending, approved, archived)
- Filterable by `status`, `category`, `source`, `workspace_id`
- Paginated via `limit` and `offset`
- Returns total count alongside results

### Update memory — `PATCH /curation/memories/{id}`
- Update `status`: `pending_review` → `approved` → `archived` (any direction)
- Update `content`: inline edit with blank-content guard
- Approving a memory makes it visible in search results

### Delete memory — `DELETE /curation/memories/{id}`
- Permanently hard-deletes a memory row

---

## MCP Tool Endpoints (`src/core/connectors/copilot.py`)

Served on the same FastAPI app — no separate process needed.

### `POST /mcp/save_memory`
- MCP tool for GitHub Copilot (VS Code agent mode) and Claude Desktop
- Accepts `content`, `source`, optional `workspace_id` and `provenance`
- Delegates to the ingest pipeline; returns 202 with session metadata

### `GET /mcp/search_memory`
- MCP tool for the same clients
- Accepts `query`, `limit`, optional `workspace_id`
- Returns approved memories only; delegates to the search pipeline

---

## Processor App (`src/processor/`)

Runs as a separate process on port 8010. Called by the core API after each ingest.

### LLM categorization
- Calls any OpenAI-compatible chat completion endpoint with a zero-temperature prompt
- Classifies content into one of four categories: `code`, `project`, `personal`, `assistant_chat`
- Falls back to heuristic categorization on any API failure or missing key

### Heuristic categorization (fallback)
- Keyword matching: code terms → `code`, project/deadline terms → `project`, preference terms → `personal`, else → `assistant_chat`
- No API key required — works offline

### Embedding
- Calls the configured LLM provider's embedding endpoint
- Stores vector as a JSON array on the `Memory` row
- Gracefully skips (stores empty vector) if no API key is configured

### Memory write
- Writes a `Memory` row with `status = pending_review`
- Stores category, embedding, and provenance (including the originating `raw_session_id`)

---

## Claude Code Connector (`connectors/claude_code/`)

Hook-driven, automatic capture — fires regardless of model behavior.

### Stop hook (Layer 1 — primary)
- Fires at the end of every Claude Code turn
- Incremental capture: reads only new transcript lines since the last checkpoint
- Checkpoint stored per session in `~/.memward/checkpoints/`
- Parses real Claude Code JSONL transcript format (user/assistant messages, tool result blocks)
- POSTs to `/ingest` with `source: claude_code` and full provenance
- Never breaks Claude Code — silently swallows all exceptions

### SessionStart hook (Layer 2 — reconciliation)
- Fires every time Claude Code opens (startup, resume, clear, compact)
- Scans all transcript files under `~/.claude/projects/` for missed lines
- Catches anything the Stop hook missed due to abrupt process kills
- Injects the most recent approved memories into the session context at startup (silent, no user-visible message)

### Filesystem sweep (Layer 3 — last resort)
- launchd plist (macOS) / cron job (Linux) running every 5 minutes
- Independent of any Claude Code hook firing
- Reuses the SessionStart hook script; catches hard process kills where no hook ran at all

---

## Claude Desktop Connector (`connectors/claude_desktop/`)

### stdio MCP bridge
- Standalone process launched by Claude Desktop via `claude_desktop_config.json`
- Exposes `save_memory` and `search_memory` as MCP tools over stdin/stdout
- Forwards all calls to the running core API at port 8000
- Best-effort capture: model-initiated or explicitly requested by the user

---

## GitHub Copilot Connector

### VS Code MCP auto-discovery (`.vscode/mcp.json`)
- Committed to the repo; VS Code picks it up automatically
- Registers the core API at `http://127.0.0.1:8000` as an HTTP MCP server
- No additional setup needed beyond having the core API running

### Copilot instructions (`.github/copilot-instructions.md`)
- Instructs Copilot when to proactively call `save_memory` and `search_memory`
- Applied to every Copilot agent session in the repo

### Always-applied memory instructions (`.github/instructions/memward-memory.instructions.md`)
- Mandates `search_memory` before the first response in every session
- Calls `save_memory` automatically on defined triggers without asking permission
- Applied via `applyTo: "**"` — covers all files

---

## Curation Web UI (`ui/`)

### Memory list
- Lists all memories with status, source, category, and creation date
- Live status counts in the sidebar (pending / approved / archived)
- Loads up to 200 items per fetch

### Filtering
- Server-side filters: status, category, source
- Client-side free-text search on memory content (no round-trip)

### Memory actions
- **Approve** — sets status to `approved`, memory becomes searchable
- **Archive** — sets status to `archived`, removes from search
- **Mark pending** — returns memory to `pending_review`
- **Edit** — inline textarea edit with save/cancel; blank content blocked
- **Delete** — confirmation dialog before permanent deletion

### Theme
- Light / dark / system theme toggle
- Preference persisted in `localStorage`
- Resolves `system` against `prefers-color-scheme`

---

## Data Model

### `memories` table
- `id`, `workspace_id` (indexed), `source`, `category`, `content`, `embedding`, `provenance` (JSON), `status`, `created_at`, `updated_at`
- `workspace_id` on every row — portability seam for future multi-tenant scaling

### `raw_sessions` table
- `id`, `workspace_id`, `source`, `s3_key` (optional), `content`, `created_at`
- Durable record of every raw ingest payload before processing

### Human review gate
- Every memory lands as `pending_review`
- Only `approved` memories are returned by search
- `archived` memories are retained but excluded from all retrieval
- Gate is enforced in two places: processor write (`status="pending_review"`) and search filter (`status == "approved"`)

---

## Not yet implemented (planned)

- pgvector similarity search (currently keyword `ILIKE`)
- SQS async processing (currently direct HTTP call — v2 upgrade path)
- Lambda / API Gateway deployment (Mangum wrapper — v2)
- Auth / API key per workspace
- Multi-workspace curation UI
