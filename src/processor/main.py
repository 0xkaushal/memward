import json
from typing import Any

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core import db as db_module
from core.config import settings
from core.db import Memory

app = FastAPI(title="memward processor API")

_llm_client: OpenAI | None = None


def _get_llm_client() -> OpenAI | None:
    api_key = settings.LLM_API_KEY or settings.ANTHROPIC_API_KEY
    if not api_key:
        return None
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            api_key=api_key,
            base_url=settings.LLM_BASE_URL,
        )
    return _llm_client


@app.on_event("startup")
def startup() -> None:
    db_module.init_db()


class ProcessMemoryRequest(BaseModel):
    raw_session_id: str = Field(..., description="Raw session ID from ingest service")
    workspace_id: str = Field(..., description="Workspace ID")
    source: str = Field(..., description="Source connector")
    content: str = Field(..., min_length=1, description="Raw memory content")
    provenance: dict[str, Any] | None = Field(None, description="Optional metadata")


class ProcessMemoryResponse(BaseModel):
    status: str
    memory_id: str
    category: str
    embedding_dims: int


_CATEGORIES = ["code", "project", "personal", "assistant_chat"]
_CATEGORY_FALLBACK_TOKENS: dict[str, list[str]] = {
    "code": ["bug", "function", "api", "refactor", "test", "class", "import"],
    "project": ["deadline", "milestone", "roadmap", "sprint", "ticket"],
    "personal": ["prefer", "style", "habit", "preference", "always", "never"],
}


def _categorize_heuristic(content: str) -> str:
    """Keyword fallback when LLM is unavailable."""
    text = content.lower()
    for category, tokens in _CATEGORY_FALLBACK_TOKENS.items():
        if any(t in text for t in tokens):
            return category
    return "assistant_chat"


def _categorize(content: str) -> str:
    """Categorize memory using LLM chat completion, falls back to heuristics."""
    client = _get_llm_client()
    if client is None:
        return _categorize_heuristic(content)
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a memory categorizer. Given a text snippet, "
                        "reply with exactly one word — the most fitting category from: "
                        "code, project, personal, assistant_chat. No explanation."
                    ),
                },
                {"role": "user", "content": content[:2000]},
            ],
            max_tokens=5,
            temperature=0,
        )
        word = resp.choices[0].message.content.strip().lower().rstrip(".")
        return word if word in _CATEGORIES else _categorize_heuristic(content)
    except Exception:
        return _categorize_heuristic(content)


def _embed(content: str) -> tuple[str, int]:
    """Generate embedding via LLM provider; returns (json_array_str, dims)."""
    client = _get_llm_client()
    if client is None:
        return "[]", 0
    resp = client.embeddings.create(
        model=settings.LLM_EMBEDDING_MODEL,
        input=content[:8000],
    )
    vector = resp.data[0].embedding
    return json.dumps(vector), len(vector)


def _get_session() -> Session:
    if db_module.SessionLocal is None:
        db_module.init_db()
    assert db_module.SessionLocal is not None
    return db_module.SessionLocal()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process-memory", status_code=202, response_model=ProcessMemoryResponse)
async def process_memory(payload: ProcessMemoryRequest) -> ProcessMemoryResponse:
    category = _categorize(payload.content)
    embedding_str, embedding_dims = _embed(payload.content)

    db = _get_session()
    try:
        memory = Memory(
            workspace_id=payload.workspace_id,
            source=payload.source,
            category=category,
            content=payload.content,
            embedding=embedding_str if embedding_dims > 0 else None,
            provenance={
                "raw_session_id": payload.raw_session_id,
                **(payload.provenance or {}),
            },
            status="pending_review",
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return ProcessMemoryResponse(
            status="accepted",
            memory_id=str(memory.id),
            category=category,
            embedding_dims=embedding_dims,
        )
    finally:
        db.close()