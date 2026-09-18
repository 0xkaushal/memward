# Product Roadmap Architecture

## Product framing

memward should be treated as a shareable developer product, not only a
personal memory layer. The near-term goal is that one developer can hand
it to another developer, that developer can connect their supported AI
tools, and the system works without architecture-level handholding.

This does **not** change the core product differentiators already locked
in elsewhere:
- human-curated review gate before retrieval
- connector-first architecture
- self-hosted, developer-controlled deployment
- cross-tool continuity across Claude Code, Copilot, and Claude Desktop

It **does** change what counts as a successful v1. A technically correct
backend is not enough if another developer cannot install, trust, and use
it quickly.

## Target product phases

### Phase 1

Self-hosted memory layer for individual developers.

Definition of success:
- a developer can deploy or run memward with a single supported setup path
- they can connect Claude Code, Copilot agent mode, and Claude Desktop
- they can inspect pending memories before those memories influence search
- they can verify health and debug connector failures without reading the
  codebase

### Phase 2

Shared workspace memory for small engineering teams.

This phase can build on the existing portability seams already preserved in
the architecture, especially `workspace_id`, connector isolation, and thin
auth boundaries. It should not be treated as the initial adoption target.

## Architectural implication

The current architecture remains valid, but roadmap priority shifts from
"single-user correctness only" to "shareable, trustworthy developer
experience."

The most important architecture-level consequences are:

### 1. Onboarding becomes a first-class system requirement

The product must have one clear, documented setup path. Another developer
should not need to assemble the system from planning notes.

Required deliverables:
- `.env.example` with every required variable documented
- one supported local or self-hosted bootstrap flow
- connector setup instructions for Claude Code, Copilot, and Claude Desktop
- a health check or smoke test proving ingest, processing, and retrieval are
  live

### 2. Trust boundaries must be explicit in the product surface

If another developer is asked to use memward, they need clear answers to:
- what gets stored
- whether raw sessions are stored
- when memories become searchable
- how they review, approve, edit, archive, or delete memories
- whether external LLMs process their content

This makes the review gate more than an internal architecture decision; it
is a product trust feature that should be visible in the UI and docs.

### 3. Self-hosted individual use comes before shared hosted usage

The recommended first distribution model is:
- one developer, self-hosted instance
- optional small shared deployment later

This keeps privacy, trust, and operational complexity manageable while the
core memory workflow is proven.

### 4. Shared-workspace readiness still matters, but as a preserved seam

The project should continue preserving:
- `workspace_id` on all rows
- server-side workspace resolution
- thin auth abstraction
- portable Postgres access

These are still necessary, but the immediate product goal is not full org
administration or multi-tenant UI. The goal is that sharing the product
with another developer does not require a rewrite.

## Revised v1 priorities

When roadmap tradeoffs appear, prioritize these in order:

1. End-to-end correctness of capture -> candidate extraction -> review ->
   approved-only retrieval
2. Fast, repeatable onboarding for a new developer
3. Clear review and deletion controls that make stored memory auditable
4. Connector setup reliability and diagnostics
5. Hosted/AWS polish beyond what is needed to support the supported install
   path

## What should not change because of this shift

This product-direction change does not justify expanding v1 into:
- browser-extension capture
- full multi-tenant team administration
- broad enterprise auth and permission systems
- automatic deduplication or contradiction resolution
- multiple vector stores

The core discipline remains: keep the seams that make later expansion
possible, but do not build the later expansion early.

## Product statement

Working positioning statement:

> A self-hosted memory layer for AI coding tools that developers can audit
> before it influences future conversations.

This statement should guide roadmap decisions and documentation tone until a
more public product narrative is chosen.
