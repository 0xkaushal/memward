# Session Handoff: Backend Infrastructure (Days 1–2)

## Completed

### Week 1 — Backend Setup

**Core Scaffold (Day 0–1):**
- ✅ FastAPI app at `src/core/main.py` with router structure
- ✅ Four route modules: root (`/`), health (`/health`), ingest (`POST /ingest`), search (`GET /search`)
- ✅ `uv` as package manager with `pyproject.toml`
- ✅ `.env.example` with all required config keys
- ✅ Git ignored with `.gitignore`

**Database Infrastructure (Day 1–2):**
- ✅ SQLAlchemy ORM models in `src/core/db.py`:
  - `Memory` table: id, workspace_id, source, category, content, embedding, provenance, status, created_at, updated_at
  - `RawSession` table: id, workspace_id, source, s3_key, content, created_at
- ✅ Environment config in `src/core/config.py` with validation
- ✅ Database connection management with session dependency injection

**Route Implementation:**
- ✅ `/ingest` (POST): Accepts raw memory from MCP or webhook, stores to raw_sessions table, returns 202 Accepted with session_id
  - Validates source field
  - Stores raw payload in raw_sessions
  - TODO: Queue to SQS for async Processing Lambda (stubbed with comment)
- ✅ `/search` (GET): Keyword search on approved memories filtered by workspace_id and status
  - Simple SQL LIKE search for v1
  - TODO: Embed query + pgvector similarity search

## Next Steps (Day 2–3)

### Critical Blockers

1. **Supabase Project Setup** (Days 1–2 blocker)
   - Go to https://supabase.co and create a new project
   - Enable pgvector extension: in project settings, go to Extensions and search "vector", enable it
   - Get credentials: Project URL and anon key from Settings → API
   - Get database URL: Settings → Database → Connection strings → Postgres (URI)
   - Copy to `.env`: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_DB_URL`
   - Once URL is set, routes will initialize database on first request

2. **Dependencies Install**
   ```bash
   uv sync  # Installs sqlalchemy, pydantic-settings, psycopg2-binary, etc.
   ```

### Immediate Next Tasks

1. **Verify ingest works end-to-end** (after Supabase is set up):
   ```bash
   curl -X POST http://127.0.0.1:8000/ingest \
     -H 'content-type: application/json' \
     -d '{"source":"copilot","content":"test memory"}'
   ```
   Should return 202 with session_id (stored in raw_sessions table)

2. **Verify search works** (after at least one memory is in approved status):
   ```bash
   curl 'http://127.0.0.1:8000/search?query=test&limit=5'
   ```

3. **Add SQS integration** for async extraction (stubbed in ingest.py):
   - boto3 for AWS SDK
   - Send message with raw_session_id, workspace_id, source to queue
   - Processing Lambda will consume from SQS (separate repo, not in this FastAPI app)

4. **Implement Anthropic embedding** for `/search`:
   - Replace keyword LIKE search with actual embedding
   - Call Anthropic API to embed query
   - Use pgvector similarity search instead of text search

### Known Deviations from Build Order

- The `status = pending_review` gate is already in the schema but not yet wired to the Processing Lambda
- Search currently uses keyword matching, not vector embeddings
- SQS queueing is commented out, waiting for AWS credentials setup

## Architecture Verified

The current setup follows AGENTS.md:
- ✅ Single FastAPI app for both MCP server and ingestion API
- ✅ Stateless routes (no file I/O, no AWS calls yet)
- ✅ Data model with workspace_id portability for later multi-tenant scaling
- ✅ Database access abstraction (easy to swap Supabase for self-hosted RDS later)
- ✅ Minimal dependencies (sqlalchemy + pydantic only for data layer)

No Dockerfile, no multi-provider LLM support, no deduplication engine — all per spec.
