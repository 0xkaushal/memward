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
| [Supabase](https://supabase.com) account | — | Free tier is sufficient |
| LLM API key | — | OpenRouter, Anthropic, or any OpenAI-compatible provider |

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/your-org/memward.git
cd memward
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Install UI dependencies

```bash
cd ui && npm install && cd ..
```

### 4. Set up Supabase

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Enable the pgvector extension: **Project Settings → Extensions → search "vector" → Enable**
3. Get your credentials from **Settings → API**:
   - Project URL → `SUPABASE_URL`
   - Anon key → `SUPABASE_KEY`
4. Get the database URL from **Settings → Database → Connection string → URI** → `SUPABASE_DB_URL`

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres
LLM_API_KEY=sk-...          # your LLM provider API key
LLM_BASE_URL=https://openrouter.ai/api/v1   # or https://api.anthropic.com/v1
LLM_CHAT_MODEL=openai/gpt-4o-mini
LLM_EMBEDDING_MODEL=openai/text-embedding-3-small
```

AWS keys (`AWS_S3_BUCKET`, `AWS_SQS_QUEUE_URL`) are optional for local development.

---

## Running locally

You need **three terminals** running simultaneously.

### Terminal 1 — Core API (port 8000)

```bash
uv run uvicorn core.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Handles ingestion, search, curation, and MCP tool endpoints.
Auto-creates database tables on first start.

### Terminal 2 — Processor (port 8010)

```bash
uv run uvicorn processor.main:app --app-dir src --host 127.0.0.1 --port 8010 --reload
```

Handles LLM categorization and embedding. Called automatically by the core API after each ingest.

### Terminal 3 — Curation UI (port 5173)

```bash
cd ui && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to review, approve, and manage memories.

---

## Verify it works

```bash
# Ingest a test memory
curl -X POST http://127.0.0.1:8000/ingest \
  -H 'content-type: application/json' \
  -d '{"source":"copilot","content":"test memory — preferred language is Python"}'
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

See [docs/claude-code-hooks.md](docs/claude-code-hooks.md) for hook installation instructions.

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
- **Database:** Supabase (Postgres + pgvector)
- **Embeddings/categorization:** Any OpenAI-compatible LLM provider
- **UI:** React 19 + Vite
- **Package manager:** uv (Python), npm (UI)
