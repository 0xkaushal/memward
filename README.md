# memward

A self-hosted memory layer for AI coding tools. Captures facts, decisions, and context across sessions and across tools — Claude Code, GitHub Copilot, and Claude Desktop — with a human review gate so you control exactly what gets remembered.

## How it works

1. AI tools call `save_memory` (via MCP or a hook) — content lands as `pending_review`
2. You review and approve memories in the curation UI
3. Approved memories are injected back into future sessions automatically

Only approved memories ever feed into retrieval. Nothing leaks without your sign-off.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Python package manager |
| Node.js | 18+ | For the curation UI |
| npm | 9+ | Comes with Node |
| LLM API key | — | OpenRouter, Anthropic, or any OpenAI-compatible provider |

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/0xkaushal/memward.git
cd memward
```

### 2. Run the installer

```bash
bash install.sh
```

This installs memward under `~/.memward/app` and installs the `memward` CLI
under `~/.local/bin/memward`.

If `memward` is not found after install, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### 3. Initialize memward

```bash
memward init
```

During init, memward will:
- ask for install mode
- ask for database choice
- ask for your `LLM_API_KEY`
- ask which agent to connect
- automatically install Claude Code hooks into `~/.claude/settings.json`

For the simplest first run, choose:
- install mode: `local`
- database: `local`
- agent: `claude-code`

If you choose `supabase` as the database, memward will also ask for
`SUPABASE_DB_URL`.

### 4. Start memward

```bash
memward start
```

This starts:
- core API on `http://127.0.0.1:8000`
- processor API on `http://127.0.0.1:8010`

The curation UI is available at:
- `http://127.0.0.1:5173`

---

## Local mode

Local mode is the default onboarding path for a single developer.

It stores state under `~/.memward/`, including:
- `~/.memward/memward.db` — local SQLite database
- `~/.memward/checkpoints/` — Claude Code hook checkpoints
- `~/.memward/logs/` — local logs

Local mode uses:
- SQLite for storage
- keyword search for retrieval
- the same `pending_review` -> `approved` memory flow

You do not need Supabase for local mode.

---

## Hosted database option

If you want a hosted Postgres path instead of local mode, choose `supabase`
for the database during `memward init` and provide `SUPABASE_DB_URL`.

You can get that from Supabase here:

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Enable the pgvector extension: **Project Settings → Extensions → search "vector" → Enable**
3. Get the database URL from **Settings -> Database -> Connection string -> URI** -> `SUPABASE_DB_URL`

---

## Running locally

For normal use:

```bash
memward start
```

For manual development without the CLI wrapper, you can still use:

```bash
./start.sh
```

---

## Verify it works

```bash
# Ingest a test memory
curl -X POST http://127.0.0.1:8000/ingest \
  -H 'content-type: application/json' \
  -d '{"source":"claude_code","content":"test memory - preferred language is Python"}'
# Should return 202 with a session_id

# Search approved memories
curl 'http://127.0.0.1:8000/search?query=python&limit=5'
# Returns empty until you approve the memory in the curation UI
```

---

## Connecting your AI tools

### GitHub Copilot (VS Code agent mode)

`.vscode/mcp.json` is already committed to this repo. VS Code will discover the real Streamable HTTP MCP server at `http://127.0.0.1:8000/mcp` when the core API is running. No additional setup needed.

### Claude Desktop

See [docs/claude-desktop-setup.md](docs/claude-desktop-setup.md) for the registration config snippet.

### Claude Code

If you selected `claude-code` during `memward init`, hook setup is already done automatically.

You can verify it with:

```bash
cat ~/.claude/settings.json
```

For manual hook details, see [docs/claude-code-hooks.md](docs/claude-code-hooks.md).

---

## Project structure

```
memward/
├── src/
│   ├── core/               # Main FastAPI app (API + MCP tools)
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── routes/
│   │   │   ├── ingest.py
│   │   │   ├── search.py
│   │   │   ├── curation.py
│   │   │   └── health.py
│   │   └── connectors/
│   │       └── copilot.py  # MCP tool endpoints
│   └── processor/          # Embedding + categorization app
│       └── main.py
├── connectors/
│   ├── claude_code/        # Stop + SessionStart hooks
│   └── claude_desktop/     # stdio MCP bridge
├── ui/                     # React curation web app
├── .env.example
└── pyproject.toml
```

---

## Tech stack

- **Backend:** FastAPI + SQLAlchemy + psycopg2
- **Database:** SQLite in local mode, or Supabase/Postgres in hosted mode
- **Embeddings/categorization:** Any OpenAI-compatible LLM provider
- **UI:** React 19 + Vite
- **Package manager:** uv (Python), npm (UI)
