# AGENTS.md

This file is the entry point for any coding agent working on this repo
(Claude Code, GitHub Copilot, or anything else that reads `AGENTS.md` by
convention). Read this in full before writing any code — there is no
code yet, this project is at the architecture/planning stage, and this
file is the plan.

Project working name: **memward** (unconfirmed — verify
`github.com/memward`, `pypi.org/project/memward`, and
`npmjs.com/package/memward` are actually unclaimed before treating the
name as final; if taken, treat every reference to "memward" below as a
placeholder to find-and-replace).

## What this project is

An independent, self-hosted memory layer that sits underneath multiple
AI tools — Claude Code, GitHub Copilot, Claude Desktop, and (later)
internal chatbots — so context persists across sessions and across
which specific tool you happen to be using at the time.

It is explicitly **not** trying to out-engineer existing players
(Supermemory, Mem0, OpenMemory) on automatic extraction quality. The
differentiator is:

1. **Human-curated review gate** — memories land as `pending_review`
   and only feed back into live retrieval once approved. Nobody else
   in this space treats "what does it actually remember" as something
   a human should routinely audit, not just trust.
2. **Connector-first architecture** — adding a new source (a new
   internal chatbot, say) should be a small, isolated adapter, not a
   change to core logic. This is what makes "scale to org later"
   plausible without a rewrite.

## Current phase: single-user, AWS-based, 2-week build budget

Built for one person (the repo owner) first. Designed so that scaling
to a multi-user/org deployment later is a config change, not a
rewrite — see "Decisions that must stay portable" below for exactly
which seams matter.

## Architecture

```
Claude Code ──┐
Copilot ──────┼──(MCP tool calls: save_memory / search_memory)──► FastAPI app
                                                                    (local: uvicorn)
                                                                    (prod: Mangum → Lambda)
                                                                          │
                                                                          ▼
                                                                   API Gateway (HTTP API)
                                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                           ▼                           ▼
                     /ingest route              /search route              Curation Web App
                     (same FastAPI app)          (same FastAPI app,        (S3 + CloudFront)
                              │                    reads Postgres)
                              ▼
                        SQS Queue
                              │
                              ▼
                   Processing Lambda (async,
                   plain function, not FastAPI)
                   - calls Anthropic API to
                     extract/categorize
                              │
                              ▼
                   Supabase Postgres + pgvector
                   (workspace_id on every row)
```

### Components

| Component | Tech choice | Why |
|---|---|---|
| MCP server + ingestion API (`save_memory` / `search_memory` / `POST /ingest`) | **Single FastAPI app**, run locally via `uvicorn`, deployed to Lambda via **Mangum** (`handler = Mangum(app)`), fronted by API Gateway (HTTP API) | One codebase for local dev and production. `uvicorn --reload` locally gives instant feedback + free auto-generated docs at `/docs` for manually testing tool calls before wiring up Claude Code. Same app, wrapped with Mangum, becomes the Lambda handler unchanged. Stateless by construction either way — no sticky-session bugs. |
| Async processing (LLM extraction + categorization) | SQS queue + Lambda worker (plain function, not FastAPI — this one's just a queue consumer) | Decouples "session ended" from the LLM call; retries come free via SQS redrive policy |
| Storage | **Supabase** (Postgres + pgvector + Auth) | Fast to start; real Postgres underneath, portable to self-hosted RDS later (see portability notes) |
| Raw session archive (optional) | S3 | Cheap insurance — lets you re-run extraction later with a better prompt without needing the original session again |
| Secrets (Anthropic API key, DB creds) | Secrets Manager (prod) / `.env` file (local) | Standard pattern already used elsewhere in this stack |
| Curation web app | Static build on S3 + CloudFront, calling the same FastAPI app's routes | Cheapest hosting for low personal-scale traffic; same shape reusable for org version |

**Note on future container/self-hosting path:** because the MCP server
and ingestion API are a plain FastAPI app, a self-hosted deployment
later (Docker container running `uvicorn`, no Mangum involved) reuses
the exact same `app.py` with zero duplicated logic — this was a
deliberate choice made to keep that door open cheaply, not something
to build now. Don't add a Dockerfile or Compose setup in v1 unless
explicitly asked; the point is that it's cheap *later*, not that it
should happen now.

### Data model

**`memories`**
- `id`, `workspace_id`, `source` (`claude_code` / `copilot` / `claude_desktop` / `internal_chatbot_x`)
- `category` (`code` / `project` / `personal` / `assistant_chat`)
- `content` — the extracted fact/decision, NOT the raw transcript
- `embedding` — pgvector column
- `provenance` — session id, tool, timestamp, git branch/repo if applicable
- `status` — `pending_review` / `approved` / `archived` (this is the curation gate — the actual product differentiator, don't cut it to save time)
- `created_at`, `updated_at`

**`raw_sessions`**
- `id`, `workspace_id`, `source`, `s3_key`, `created_at`

Deliberately just these two tables for v1. No dedupe/contradiction-resolution engine — the review gate is the substitute (bad or duplicate memories simply don't get approved).

### Flows

**Ingestion → storage:** agent/tool calls `save_memory` (MCP) or
`POST /ingest` (webhook) → FastAPI app writes raw payload to S3, drops a
message on SQS, returns immediately → Processing Lambda (async) calls
the Anthropic API to extract facts + assign category → writes a
`memories` row with `status = pending_review`.

**Retrieval:** agent calls `search_memory(query)` → FastAPI app embeds the
query → pgvector similarity search filtered to `status = approved` AND
`workspace_id` → returns top-N matches. Unreviewed memories never leak
into a live session — this filter is not optional.

## Decisions that must stay portable (do not casually change these)

These are the seams that make "single-user now, org later" actually
work without a rewrite. Preserve them even under time pressure:

1. **`workspace_id` on every table row**, even though today there's
   only one workspace value in practice. Removing this "because it's
   unused right now" defeats the entire point of designing it in early.
2. **Auth stays behind one thin abstraction.** Using Supabase Auth is
   fine and expected for speed, but the authorization check (verify
   token, extract user/workspace id) must live in exactly one small
   function/module. Don't scatter `auth.uid()` or Supabase-specific
   calls through business logic — that's what makes migrating off
   Supabase Auth later (to Cognito, Azure AD, self-hosted GoTrue,
   whatever) a one-file change instead of a rewrite.
3. **Database access goes through a plain Postgres connection string**,
   not the Supabase client SDK, for anything beyond auth itself. Use
   raw SQL or a standard ORM. This is what makes `pg_dump` /
   `pg_restore` onto self-hosted RDS later a real, low-drama option —
   AWS RDS for PostgreSQL supports pgvector too, so the vector columns
   move with the rest of the data.
4. **No RLS policies tied to `auth.uid()`** for now — do
   workspace/user filtering explicitly in query `WHERE` clauses. Plain
   SQL moves with you regardless of which auth provider is in front of
   it; Supabase-specific RLS helpers do not.
5. **Connector logic stays isolated per source** (small adapter per
   tool: Claude Code, Copilot, Claude Desktop, future internal
   chatbots). Don't let source-specific parsing bleed into the core
   ingestion/processing/retrieval logic — that isolation is the actual
   "connector-first" differentiator, not just a nice-to-have.
6. **The MCP server and ingestion API are one FastAPI app, deployed via
   Mangum.** Don't split this into raw per-route Lambda handlers, and
   don't add a Dockerfile/Compose setup yet — the whole point of this
   choice is that local dev (`uvicorn`), production (Mangum → Lambda),
   and a future self-hosted container all reuse the exact same `app.py`
   with zero duplicated logic. Splitting it up now to "optimize" either
   side throws that away for no benefit at current scale.

## Explicitly out of scope for v1 — do not add without discussion

- **Pinecone or any separate vector database.** Supabase's pgvector
  covers this at current scale. Adding a second vector store means two
  systems that can silently drift out of sync — don't reintroduce that
  risk for no clear payoff.
- **Dedupe/contradiction-resolution engine.** The `status` review gate
  substitutes for this. Don't build this until the review gate proves
  insufficient in practice.
- **Aurora Serverless v2 / self-hosted RDS.** Supabase now; migrate
  only if a concrete requirement (data sovereignty, cost at real scale)
  forces it — see portability notes above for how that migration should
  work when it happens.
- **Multi-provider LLM support** (OpenAI-compatible adapter, etc.).
  Anthropic-only for v1.
- **Real multi-tenant UI / team management.** `workspace_id` exists in
  the schema; building actual team/invite/role UI is a later phase.
- **Dockerfile / docker-compose / container deployment.** The FastAPI +
  Mangum split already keeps this door open cheaply for later — see
  "Decisions that must stay portable" above. Building it now is
  premature for a single-user, 2-week v1.

## Build order (2-week budget)

**Week 1 — backend, no UI**
- Days 1–2: Supabase project set up, pgvector enabled, schema created, `.env` wired for local secrets
- Days 3–4: FastAPI app — `save_memory`, `search_memory`, `/ingest` routes, running locally via `uvicorn --reload`; SQS + Processing Lambda for async extraction (budget extra time here — most moving pieces)
- Day 5: Wrap the same FastAPI app with Mangum, deploy behind API Gateway, test `save_memory`/`search_memory` from Claude Code against the deployed Lambda

**Week 2 — curation UI + second connector**
- Days 6–8: Curation web app (list/filter by category/source, approve/edit/delete) — the actual differentiator, don't rush it
- Days 9–10: Second connector (Copilot, via its MCP agent-mode tool support) — proves the adapter pattern generalizes
- Days 11–12: Buffer (IAM/OAuth permission issues reliably eat a day)
- Days 13–14: Polish, README, decide on public/open-source posture

## Known competitive landscape (context, not a blocker)

Worth knowing so nothing here gets built under the illusion it's
unprecedented: **Supermemory**, **Mem0** ("the universal memory layer
for AI agents"), and **OpenMemory** (self-hosted, already supports
Claude Desktop + GitHub Copilot + Codex + MCP) all occupy this space
already, with real GitHub traction and, in Supermemory's case, funding
and a published benchmark suite. This project's reason to exist is the
human-curation-gate + connector-first angle specifically — if a build
decision would sacrifice either of those to save time, flag it rather
than silently cutting it, since that's the whole differentiation.

## If you are a coding agent picking this up cold

1. Confirm which day/phase of the build order (above) is actually
   in progress — check for a `docs/SESSION_HANDOFF.md` if one exists
   yet; if not, this repo is likely still at day 0 and you're
   scaffolding from scratch per this file.
2. Do not skip the `status = pending_review` gate "to simplify" — it's
   the product's reason to exist, not an incidental detail.
3. Do not add Pinecone, a second LLM provider, or real multi-tenant
   auth without the human explicitly asking for it in this session —
   see "Explicitly out of scope" above.
4. When in doubt about a naming or scope decision not covered here,
   ask rather than assume — this file reflects a plan discussed and
   agreed on prior to any code existing, not a spec handed down
   unilaterally.
