import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core import db as db_module
from core.config import settings
from core.db import Memory, RawSession

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


class ProcessMemoryResponse(BaseModel):
    status: str
    memory_ids: list[str]
    embedding_dims: int


class ProcessPendingResponse(BaseModel):
    processed_sessions: int


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


def _extract_candidates(content: str) -> list[tuple[str, str]]:
    """Return concise reviewable facts, never a raw transcript dump."""
    client = _get_llm_client()
    if client is not None:
        try:
            response = client.chat.completions.create(
                model=settings.LLM_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract durable, atomic memories from the input. Return JSON only: "
                            '{"memories":[{"content":"...","category":"code|project|personal|assistant_chat"}]}. '
                            "Include only facts, decisions, preferences, or constraints worth reviewing. "
                            "Never return a transcript, dialogue labels, or more than 8 items."
                        ),
                    },
                    {"role": "user", "content": content[:12000]},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content or "{}")
            candidates = []
            for item in parsed.get("memories", [])[:8]:
                text = str(item.get("content", "")).strip()
                category = str(item.get("category", ""))
                if text and len(text) <= 1000 and category in _CATEGORIES:
                    candidates.append((text, category))
            if candidates:
                return candidates
        except Exception:
            pass

    # MCP callers normally supply one distilled fact. Do not convert a captured
    # multi-turn transcript into a single misleading memory when extraction is
    # unavailable.
    normalized = content.strip()
    if "\n[" not in normalized and len(normalized) <= 500:
        return [(normalized, _categorize_heuristic(normalized))]
    return []


def _get_session() -> Session:
    if db_module.SessionLocal is None:
        db_module.init_db()
    assert db_module.SessionLocal is not None
    return db_module.SessionLocal()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process-memory", status_code=202, response_model=ProcessMemoryResponse)
def process_memory(payload: ProcessMemoryRequest) -> ProcessMemoryResponse:
    db = _get_session()
    try:
        raw = db.query(RawSession).filter(RawSession.id == payload.raw_session_id).first()
        if raw is None or raw.workspace_id != payload.workspace_id or raw.source != payload.source:
            raise ValueError("Raw session not found for this processing request")
        if raw.processing_status == "processed":
            existing = db.query(Memory).filter(Memory.raw_session_id == raw.id).all()
            return ProcessMemoryResponse(
                status="processed",
                memory_ids=[str(memory.id) for memory in existing],
                embedding_dims=0,
            )

        raw.processing_status = "processing"
        raw.processing_attempts += 1
        raw.processing_started_at = datetime.now(timezone.utc)
        db.commit()

        candidates = _extract_candidates(raw.content)
        memories: list[Memory] = []
        embedding_dims = 0
        for candidate_index, (content, category) in enumerate(candidates):
            embedding_str, dims = _embed(content)
            embedding_dims = max(embedding_dims, dims)
            memory = Memory(
                workspace_id=raw.workspace_id,
                source=raw.source,
                category=category,
                content=content,
                embedding=embedding_str if dims > 0 else None,
                provenance={"raw_session_id": raw.id, **(raw.provenance or {})},
                raw_session_id=raw.id,
                candidate_index=candidate_index,
                status="pending_review",
            )
            db.add(memory)
            memories.append(memory)

        raw.processing_status = "processed"
        raw.processing_error = None
        raw.processed_at = datetime.now(timezone.utc)
        db.commit()
        for memory in memories:
            db.refresh(memory)
        return ProcessMemoryResponse(
            status="processed",
            memory_ids=[str(memory.id) for memory in memories],
            embedding_dims=embedding_dims,
        )
    except Exception as exc:
        db.rollback()
        raw = db.query(RawSession).filter(RawSession.id == payload.raw_session_id).first()
        if raw is not None:
            raw.processing_status = "failed"
            raw.processing_error = str(exc)[:2000]
            db.commit()
        raise
    finally:
        db.close()


@app.post("/process-pending", response_model=ProcessPendingResponse)
def process_pending(limit: int = 10) -> ProcessPendingResponse:
    """Process durable jobs left pending after a transient dispatch failure."""
    db = _get_session()
    try:
        jobs = (
            db.query(RawSession)
            .filter(RawSession.processing_status.in_(("pending", "failed")))
            .order_by(RawSession.created_at.asc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        payloads = [
            ProcessMemoryRequest(
                raw_session_id=str(job.id),
                workspace_id=job.workspace_id,
                source=job.source,
            )
            for job in jobs
        ]
    finally:
        db.close()

    completed = 0
    for payload in payloads:
        try:
            process_memory(payload)
            completed += 1
        except Exception:
            continue
    return ProcessPendingResponse(processed_sessions=completed)
