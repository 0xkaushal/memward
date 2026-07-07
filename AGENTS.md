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
which specific tool you happen to be using at the time. Capture
reliability differs meaningfully by source (Claude Code is
deterministic via hooks; Copilot and Claude Desktop are best-effort via
MCP tool calls) — see "Capture mechanisms" below before assuming
uniform behavior across sources.

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
                   Processor FastAPI app
                   (v1: direct HTTP call;
                    v2: SQS → Lambda)
                   - embed + categorize
                   - write pending_review
                              │
                              ▼
                   Supabase Postgres + pgvector
                   (workspace_id on every row)
```

### Components

| Component | Tech choice | Why |
|---|---|---|
| MCP server + ingestion API (`save_memory` / `search_memory` / `POST /ingest`) | **Single FastAPI app**, run locally via `uvicorn`, deployed to Lambda via **Mangum** (`handler = Mangum(app)`), fronted by API Gateway (HTTP API) | One codebase for local dev and production. `uvicorn --reload` locally gives instant feedback + free auto-generated docs at `/docs` for manually testing tool calls before wiring up Claude Code. Same app, wrapped with Mangum, becomes the Lambda handler unchanged. Stateless by construction either way — no sticky-session bugs. |
| Processing (LLM extraction + categorization) | **v1:** Second FastAPI app (`processor`) called directly over HTTP from `/ingest` (best-effort, fire-and-forget with a short timeout). **v2 upgrade path:** swap the HTTP call for an SQS message drop + Lambda consumer — the processor FastAPI app can be reused as the handler body unchanged. | v1 keeps the deployment simple and removes the AWS-credential dependency during development. The upgrade seam (a single HTTP call in `ingest.py`) is small and isolated. |
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
`POST /ingest` (webhook) → FastAPI app writes raw payload to `raw_sessions`, then
makes a best-effort HTTP POST to the **processor FastAPI app** (`POST /process-memory`)
and returns 202 immediately. The processor embeds the content, assigns a category,
and writes a `memories` row with `status = pending_review`.

> **v1 vs v2 note:** The direct HTTP call is intentional for v1 to keep AWS
> dependencies out of local dev. The upgrade path to SQS + Lambda is a one-seam
> change in `ingest.py` — the processor logic itself does not need to change.

**Retrieval:** agent calls `search_memory(query)` → FastAPI app embeds the
query → pgvector similarity search filtered to `status = approved` AND
`workspace_id` → returns top-N matches. Unreviewed memories never leak
into a live session — this filter is not optional.

### Capture mechanisms (how content actually reaches `/ingest`)

This is the part that's easy to hand-wave and easy to get wrong. Claude
Code, Copilot, and Claude Desktop need genuinely different mechanisms —
not just different parsing of a similarly-shaped input. Do not assume a
uniform "connector" interface that ignores this asymmetry.

**Summary — confirmed and locked in:**

| Source | Capture mechanism | How it fires |
|---|---|---|
| Claude Code | Hooks (`Stop` primary, `SessionStart` reconciliation, filesystem sweep last resort) | Automatic, deterministic — fires regardless of what the model does or decides |
| GitHub Copilot (VS Code, **agent mode specifically**) | MCP tool call (`save_memory`) | Best-effort — either the model decides to call it, or the person explicitly asks it to |
| Claude Desktop (regular chat) | MCP tool call (`save_memory`) | Same as Copilot — best-effort, model-initiated or explicitly requested |

**Important caveat on the Copilot row:** this only works in VS Code's
**agent mode with an MCP server configured** — the specific surface
that supports MCP tool calls. Do not assume this covers Copilot's
inline autocomplete or other IDE integrations (Visual Studio,
JetBrains, etc.) unless separately confirmed to also support MCP tool
calls the same way.

**The Claude Code / (Copilot + Claude Desktop) reliability gap is
permanent for v1, not a bug to chase.** Claude Code's hooks fire no
matter what the model does. Copilot's and Claude Desktop's capture only
happens if the model, mid-conversation, decides to emit a `save_memory`
tool call — visible in the UI the same way any other tool call is. If
it never emits that call during a session, nothing from that session
is captured; there is no background process or file to reconcile
against afterward, unlike Claude Code's transcript-based hooks. The
only way to make this deterministic — rather than best-effort — would
be a browser-extension-style capture layer, which was deliberately
deferred (see "Deferred: browser-extension capture" below).

**Mitigation available now, not a real fix:** the person can issue an
explicit instruction ("save a summary of this conversation to memory")
at the end of a Copilot or Claude Desktop session, which still resolves
to the same `save_memory` tool call, just triggered by the person
instead of left to the model's judgment. This makes capture reliable in
the sense that the *person* controls when it fires — it does not make
it automatic.

**Claude Code — hook-driven, not a `save_memory` tool call the model
has to remember to make.**

Do NOT rely solely on the model proactively deciding to call
`save_memory`. Reliable capture comes from Claude Code's own hook
system, layered three ways so no single failure mode loses data:

1. **`Stop` hook (primary path).** Fires at the end of *every turn*,
   not just at session end. On each fire, read whatever's new in
   `transcript_path` since the last checkpoint and enqueue it (push to
   `/ingest`, fast, no blocking on LLM extraction — extraction happens
   later, async, off the SQS queue already in this architecture). This
   gives near-real-time, incremental capture throughout the day, and
   means a hard laptop-close mid-conversation loses at most the last
   unfinished turn.
2. **`SessionStart` hook (reconciliation).** Fires next time Claude
   Code is opened (`source` values: `startup`, `resume`, `clear`,
   `compact`). On fire, scan `~/.claude/projects/` for transcript files
   modified since the last known checkpoint that never got fully
   enqueued, and catch them up. This covers whatever the `Stop` hook
   missed — e.g. if the process was killed between turns.
3. **Filesystem sweep (last resort, no hook dependency at all).** A
   small background job (launchd / scheduled task / cron depending on
   OS) running every few minutes, checking transcript file
   modification times independent of any Claude Code event firing.
   Covers a fully abrupt process kill where no hook gets to run at all.

Rationale for NOT using `SessionEnd` as the primary mechanism: it only
fires on clean exit, sigint, or error — a process that gets killed
outright (lid-close suspend behaving oddly, terminal force-quit,
dropped SSH connection) never gets to run it. Treating `SessionEnd` as
the main capture point would silently lose exactly the kind of session
end this project's actual user has (walks away, doesn't run `/exit`).

**GitHub Copilot and Claude Desktop — no equivalent hook exists for
either. Do not build one.**

Neither has a documented, stable event comparable to Claude Code's
`Stop`/`SessionStart`/`SessionEnd`. Real options, and the first is the
one to build first, for both sources:

1. **Explicit MCP tool-call approach (build this first, for both
   Copilot and Claude Desktop).** Both support MCP tools — Copilot in
   VS Code's agent mode specifically (see caveat in the summary table
   above), Claude Desktop via its own MCP config. Instruct the model,
   via `.github/copilot-instructions.md` (Copilot) and Claude Desktop's
   equivalent custom-instructions surface, to proactively call
   `save_memory` when it judges something worth remembering. Less
   complete than Claude Code's capture (depends on the model choosing
   to call the tool, or the person explicitly asking it to) but uses
   only documented, stable interfaces — nothing to maintain against
   undocumented internals.
2. **File-watcher on local chat session storage (v2 idea, not v1,
   Copilot-specific).** VS Code's Copilot chat history is saved locally
   as JSON under `workspaceStorage/<hash>/chatSessions/`. A watcher
   could detect changes and ingest automatically. Don't build this in
   v1 — the format is undocumented and has already shifted across VS
   Code versions (the manual "Chat: Export Session" command itself has
   reportedly disappeared in some Insiders builds), so it's a
   maintenance liability, not a quick win. No equivalent exists for
   Claude Desktop's regular chat — see "Deferred: browser-extension
   capture" below for why that gap is not being closed in v1 either.

### Deferred: browser-extension capture (considered, deliberately not building this)

This was seriously discussed and explicitly deferred, not overlooked —
don't rediscover it mid-build and treat it as a quick win. Tools like
Supermemory and Mem0 close the Claude.ai/ChatGPT web-chat gap with a
browser extension: a content script that reads the rendered chat page
directly, independent of any API or hook, capturing every message in
real time. This would also be the way to make Claude Desktop's regular
chat capture deterministic instead of best-effort.

Deliberately not building this for v1, for two reasons that are both
real, not just time pressure:

1. **Trust surface.** A content script reading everything typed into
   Claude.ai or Claude Desktop is mechanically the same thing as a
   keylogger for AI conversations. For a project whose actual
   differentiator is a human-curated, trustworthy memory layer,
   shipping something that reads that way deserves its own deliberate
   decision, not an incidental feature add.
2. **Scope.** Manifest V3 extension development, DOM-scraping logic
   with no stable contract (breaks whenever the target site's frontend
   changes), and Chrome Web Store publishing are each their own
   multi-week effort — this is not a "connector," it's a separate
   project.

If this gets revisited later, it should be its own explicit
conversation about whether the trust trade-off is worth it — not a
default fallback reached for because MCP tool-call capture feels
incomplete.

**Net implication for `AGENTS.md`'s "connector" concept above:**
"connector" does not mean one uniform interface per source. Each
source's connector is whatever capture mechanism is actually robust
for that specific tool — a hook-driven background pipeline for Claude
Code, a model-initiated (or person-initiated) tool call for Copilot and
Claude Desktop. Keep this asymmetry explicit rather than trying to
force a single abstraction that doesn't fit all three.

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
7. **Capture is hook-driven for Claude Code, not model-initiated.**
   Don't simplify Claude Code capture down to "instruct the model to
   call `save_memory`" — that's the Copilot/Claude Desktop fallback,
   chosen there specifically because nothing better exists for either
   of them without the deferred browser-extension approach. Claude Code
   has real hooks; use them (`Stop` as primary, `SessionStart` for
   reconciliation, a filesystem sweep as last resort). See "Capture
   mechanisms" above for the full rationale — this was a deliberate
   reliability decision, not an arbitrary implementation choice.

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
- Days 3–4: FastAPI app — `save_memory`, `search_memory`, `/ingest` routes, running locally via `uvicorn --reload`; separate **processor FastAPI app** that `/ingest` calls directly over HTTP for v1 (no SQS/Lambda needed locally — SQS is the v2 upgrade path, not a v1 requirement)
- Day 5: Wrap the same FastAPI app with Mangum, deploy behind API Gateway; build the Claude Code `Stop` hook script (primary capture path) and test end-to-end against the deployed endpoint

**Week 2 — curation UI + second connector**
- Days 6–8: Curation web app (list/filter by category/source, approve/edit/delete) — the actual differentiator, don't rush it
- Days 9–10: `SessionStart` reconciliation hook + filesystem sweep for Claude Code (the two reliability layers behind the `Stop` hook); Copilot connector via `.github/copilot-instructions.md` and Claude Desktop connector via its own custom-instructions surface, both instructing proactive `save_memory` calls — proves the adapter pattern generalizes across genuinely different capture mechanisms, not just different tools
- Days 11–12: Buffer (IAM/OAuth permission issues reliably eat a day; hook debugging across abrupt-kill scenarios likely eats the rest)
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
4. Do not implement Claude Code capture as "the model calls
   `save_memory` when it thinks something's worth remembering." That's
   the Copilot/Claude Desktop fallback specifically because neither has
   anything better without the deferred browser-extension approach.
   Claude Code capture must be hook-driven — see "Capture mechanisms"
   above.
5. Do not build browser-extension-style capture as a way to "fully
   solve" Copilot/Claude Desktop's best-effort capture gap without the
   human explicitly re-opening that conversation — see "Deferred:
   browser-extension capture" above for why it was set aside
   deliberately, not overlooked.
6. When in doubt about a naming or scope decision not covered here,
   ask rather than assume — this file reflects a plan discussed and
   agreed on prior to any code existing, not a spec handed down
   unilaterally.
