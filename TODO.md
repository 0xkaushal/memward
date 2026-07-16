# memward — Implementation TODO

This list turns the architecture review into an execution order. The first goal
is a trustworthy vertical slice: durable capture → extracted candidates → human
review → approved-only retrieval.

## P0 — Correctness and product promises

- [ ] Rename the project before publishing or packaging.
  - `memward` is already claimed on PyPI by an unrelated AI-memory security
    package.
  - Verify candidate names on GitHub, PyPI, and npm before choosing one.
  - Update the Python distribution name, repository references, connector
    names, documentation, and configuration paths after the new name is chosen.

- [ ] Make ingestion and processing durable, retryable, and idempotent.
  - Record a processing state, attempt count, failure detail, and timestamps on
    each raw session.
  - Create an idempotency key from source/session/offset/content checksum.
  - Persist the raw session and a processing job atomically before returning
    `202 Accepted`.
  - Run a retryable worker that processes pending/failed jobs; use the direct
    processor call for v1 if desired, but do not lose failed dispatches.
  - Ensure duplicate hook deliveries cannot create duplicate memories.
  - Keep the SQS/Lambda migration limited to replacing the dispatch seam.

- [ ] Fix Claude Code checkpoint semantics.
  - Advance a checkpoint only after the ingest service durably accepts the
    payload; remove the unconditional `if success or True` path.
  - Store byte offsets or content hashes instead of only line counts where
    practical.
  - Make SessionStart reconciliation and the filesystem sweep retry safely.
  - Add automated tests for unavailable API, timeout, restart, and duplicate
    delivery scenarios.

- [ ] Extract memory candidates instead of storing raw input as a memory.
  - Keep transcripts and raw MCP input only in `raw_sessions`.
  - Have the processor produce zero or more concise, atomic facts/decisions
    with category and extraction confidence.
  - Link every candidate to the raw session and precise provenance/excerpt.
  - Enforce a quality contract: no raw transcript dumps, bounded length, and
    one independently reviewable claim per candidate.
  - Preserve the mandatory `pending_review` default for every candidate.

- [ ] Implement a real MCP transport for Copilot.
  - The current `/mcp/save_memory` and `/mcp/search_memory` routes are REST,
    not an HTTP MCP server endpoint.
  - Expose a real Streamable HTTP MCP endpoint from the FastAPI app, or provide
    a local stdio bridge for VS Code as is already done for Claude Desktop.
  - Verify tool discovery and calls in VS Code agent mode, not only via HTTP
    requests.
  - Keep Copilot capture explicitly best-effort and do not add an unsupported
    background capture mechanism.

- [ ] Establish one server-side workspace identity boundary.
  - Add the planned thin auth/identity module now, even if v1 initially resolves
    to one configured workspace.
  - Do not let clients freely select `workspace_id` in requests.
  - Filter all reads and mutations by the resolved workspace, including lookup
    by memory ID, collection ID, and membership ID.
  - Keep business logic independent of Supabase Auth or any specific identity
    provider.

## P1 — Retrieval, schema, and deployment readiness

- [ ] Replace JSON-text embeddings and `ILIKE` retrieval with pgvector search.
  - Use a real pgvector column with a declared embedding dimension.
  - Validate the returned embedding dimension before writing.
  - Add a pgvector index suited to the expected corpus size.
  - Embed the query and retrieve nearest neighbors filtered by both
    `workspace_id` and `status = approved`.
  - Optionally add keyword retrieval later as a hybrid fallback; do not allow
    unapproved memories into either path.

- [ ] Correct the production UI build/serve path.
  - Vite currently builds to `src/ui/dist`, while FastAPI mounts `ui/dist`.
  - Choose one output path and use it in Vite, FastAPI, Makefile, README, and
    deployment configuration.
  - Add a production-build smoke test that requests the UI through FastAPI.

- [ ] Decide whether collections belong in v1.
  - The agreed v1 data model intentionally contains only `memories` and
    `raw_sessions`; collections are scope expansion.
  - If deferred, remove the feature cleanly rather than leaving an untested
    partial model.
  - If retained, fix the type mismatch between string `memories.id` and UUID
    `memory_collections.memory_id`, add workspace-scoped checks, and add
    Postgres integration tests.

- [ ] Add database migrations and Postgres-backed integration testing.
  - Replace startup `create_all()` as the production schema-management path
    with versioned migrations.
  - Test against ephemeral Postgres with pgvector enabled; SQLite cannot catch
    Postgres enum, UUID, foreign-key, vector, or index failures.
  - Cover ingest → processor → curation → approved retrieval end-to-end.
  - Cover retry/idempotency, workspace isolation, pending-memory exclusion,
    connector protocol handshakes, and production UI serving.

- [ ] Prepare the FastAPI app for the stated deployment target.
  - Add the Mangum handler required for Lambda/API Gateway deployment.
  - Use a lifespan handler instead of deprecated FastAPI startup events.
  - Set CORS from explicit environment configuration for production rather than
    local development origins only.
  - Keep the app stateless and avoid Docker/Compose work unless explicitly
    reprioritized.

## P2 — Review experience and operational clarity

- [ ] Improve review from single-memory actions to review batches.
  - Show candidate content, source, raw excerpt, provenance, category, and
    extraction confidence together.
  - Surface similar approved/pending memories to help reviewers spot duplicates.
  - Support bulk approve, archive, and edit where safe.

- [ ] Make curation reversible and auditable.
  - Add a reject/archive reason and an immutable review event history.
  - Prefer soft deletion or an explicit retention policy over irreversible hard
    deletion by default.
  - Record who/what approved, edited, archived, or deleted a memory and when.

- [ ] Add connector and pipeline health visibility.
  - Report last successful Claude Code hook capture, reconciliation run, and
    filesystem sweep.
  - Show pending processing jobs, retry counts, processing failures, and stale
    raw sessions.
  - Clearly distinguish deterministic Claude Code capture from best-effort
    Copilot/Claude Desktop capture in the UI and docs.

- [ ] Consolidate and correct project documentation.
  - Reconcile `AGENTS.md`, README, FEATURES, and the session handoff so there
    is one accurate v1 contract.
  - Resolve the current provider-policy mismatch (Anthropic-only plan versus
    OpenAI-compatible implementation/docs).
  - Document the real MCP transport and tested setup steps for each connector.
  - Update the handoff after each milestone with completed work, decisions, and
    known limitations.

## Guardrails to preserve while working

- [ ] Every memory remains scoped by `workspace_id`.
- [ ] Only `approved` memories can enter search or connector retrieval results.
- [ ] Claude Code remains hook-driven: Stop, SessionStart reconciliation, then
  filesystem sweep.
- [ ] Copilot and Claude Desktop remain explicit/best-effort MCP capture in v1.
- [ ] Keep connector-specific capture logic isolated from core ingestion,
  processing, and retrieval logic.
- [ ] Keep Postgres access portable; avoid Supabase SDK coupling and
  `auth.uid()`-based RLS policies in core business logic.
- [ ] Do not add Pinecone, a second vector database, browser-extension capture,
  deduplication/contradiction automation, Docker/Compose, or multi-tenant UI
  without an explicit scope decision.
