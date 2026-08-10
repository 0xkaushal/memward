# Session Handoff — Current State (as of Week 2)

This document reflects the actual state of the codebase. The previous
version described Days 1–2 only and is now obsolete.

---

## What Is Done

### Backend (`src/core/`)
- FastAPI app with lifespan, CORS, routers, MCP mount, static UI serving
- `save_memory` and `search_memory` MCP tools (Streamable HTTP via FastMCP at `/mcp`)
- `POST /ingest` — idempotent raw session creation, fire-and-forget dispatch to processor
- `GET /search` — keyword search on `status=approved` memories, workspace-scoped
- `GET/PATCH/DELETE /curation/memories` — full curation API with pagination and filters
- `GET/POST/PATCH/DELETE /curation/collections` + membership routes
- `workspace.py` — single portability seam for `workspace_id` (per spec)
- `ingestion.py` — SHA-256 idempotency key dedup

### Processor (`src/processor/`)
- Separate FastAPI app on port 8010
- LLM extraction via **Anthropic Claude** (`claude-3-haiku-20240307` default)
- Embedding via Voyage AI (`voyage-3` default, via `voyageai` package)
- Heuristic categorization fallback when API key absent
- State machine: `pending → processing → processed/failed` with attempt count
- `POST /process-pending` for retry of failed jobs

### Claude Code Connector (`connectors/claude_code/`)
- `stop_hook.py` — incremental JSONL transcript reading, checkpoint tracking, `/ingest` dispatch
- `session_start_hook.py` — missed-transcript reconciliation + approved memory context injection

### Claude Desktop Connector (`connectors/claude_desktop/`)
- `mcp_server.py` — stdio MCP bridge forwarding to core API

### Copilot Connector
- `.github/copilot-instructions.md` + `memward-memory.instructions.md` — always-on trigger rules
- REST adapter routes at `/mcp/save_memory` and `/mcp/search_memory`

### Curation Web UI (`ui/`)
- React app: memory list, approve/archive/edit/delete, collections sidebar, theme toggle
- Vite dev server proxies `/curation` to `http://127.0.0.1:8000`
- Production build outputs to `ui/dist/`, served by FastAPI at `/ui`

### Tests (`tests/`)
- Ingest, health, search, and curation routes — SQLite-backed, all passing

### Tooling
- `Makefile` — `install`, `dev-api`, `dev-processor`, `dev-ui`, `build`, `lint`
- `ci.yml` — GitHub Actions: Python 3.11/3.12 backend tests + UI lint/build

---

## What Is Pending / Known Gaps

### P0 (blocking correctness)
- Hook script tests (unavailable API, timeout, duplicate delivery, restart)
- Auth abstraction module (trivial impl acceptable — isolate the token-check seam)

### P1 (important before calling v1 done)
- Real pgvector similarity search — currently uses keyword `ILIKE`; embedding column is `Text`, not `VECTOR`
- Mangum wrapper for Lambda + API Gateway deployment
- Alembic migrations (currently `create_all()` on startup only)
- Postgres-backed integration tests (all tests currently run on SQLite)
- Processor app tests

### P2 (cleanup / polish)
- CORS origins via env var (`CORS_ORIGINS`) instead of hard-coded localhost
- Update TODO.md to mark resolved items (collections decision, LLM provider)
- Filesystem sweep (Layer 3): launchd plist not yet committed to repo

---

## Architecture Status vs AGENTS.md

| Constraint | Status |
|---|---|
| `workspace_id` on every row | Done |
| Auth behind one thin abstraction | Partially — `workspace.py` seam exists, no token verify yet |
| DB via plain Postgres connection string | Done |
| No RLS tied to `auth.uid()` | Done |
| Connector logic isolated per source | Done |
| MCP + ingest API = one FastAPI app (Mangum path) | App done; Mangum wrapper missing |
| Claude Code capture is hook-driven | Done |
| LLM provider is Anthropic-only | Done (fixed — was OpenRouter previously) |
| `pending_review` gate enforced | Done — processor writes it, search filters it |
| Collections accepted as v1 scope | Done — AGENTS.md updated to reflect 4-table model |
| PyPI name conflict | Accepted — self-hosted, no PyPI distribution planned |
