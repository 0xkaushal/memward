import hashlib
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core import db as db_module
from core.db import Memory

app = FastAPI(title="memward processor API")


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


def _categorize(content: str) -> str:
    text = content.lower()
    if any(token in text for token in ["bug", "function", "api", "refactor", "test"]):
        return "code"
    if any(token in text for token in ["deadline", "milestone", "roadmap", "sprint"]):
        return "project"
    if any(token in text for token in ["prefer", "style", "habit", "preference"]):
        return "personal"
    return "assistant_chat"


def _fake_embedding(content: str, dims: int = 8) -> str:
    # Deterministic lightweight embedding for POC.
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    values = []
    for idx in range(dims):
        b = digest[idx]
        values.append((b / 255.0) * 2.0 - 1.0)
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


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
    embedding = _fake_embedding(payload.content)

    db = _get_session()
    try:
        memory = Memory(
            workspace_id=payload.workspace_id,
            source=payload.source,
            category=category,
            content=payload.content,
            embedding=embedding,
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
        )
    finally:
        db.close()