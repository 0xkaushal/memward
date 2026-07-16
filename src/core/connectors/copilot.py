"""
MCP tool routes: save_memory and search_memory.

These are the endpoints Copilot (VS Code agent mode) and Claude Desktop
call as MCP tools. Per AGENTS.md, this is the best-effort capture path
for those two sources — the model initiates the call, or the person asks.

Both tools are wired on the same FastAPI app as /ingest and /search so
there is one deployment artifact, one running process.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.db import get_db
from core.routes.ingest import IngestRequest, IngestResponse, ingest_memory
from core.routes.search import SearchResponse, search_memory as _search_memory

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ── save_memory ────────────────────────────────────────────────────────────

class SaveMemoryInput(BaseModel):
    """
    MCP tool schema for save_memory.

    The model calls this when it judges something worth persisting.
    Content should be the distilled fact or decision — NOT a raw dump.
    """
    content: str = Field(
        ...,
        min_length=1,
        description="The memory to save — a concise fact, decision, or preference",
        examples=["User prefers uv for Python package management in all projects."],
    )
    source: str = Field(
        "copilot",
        description="Source connector (copilot, claude_desktop, etc.)",
        examples=["copilot"],
    )
    workspace_id: Optional[str] = Field(
        None,
        description="Workspace ID — defaults to WORKSPACE_ID in config",
    )
    provenance: Optional[dict[str, Any]] = Field(
        None,
        description="Optional metadata (session context, file, branch, etc.)",
    )


class SaveMemoryResult(BaseModel):
    """Response returned to the MCP caller."""
    status: str
    session_id: str
    workspace_id: str
    source: str
    processor_dispatch: str


@router.post(
    "/save_memory",
    status_code=202,
    response_model=SaveMemoryResult,
    summary="Save a memory (MCP tool)",
    description=(
        "MCP tool called by Copilot or Claude Desktop to persist a memory. "
        "The raw payload is stored immediately and forwarded to the processor "
        "for embedding and categorization. Returns 202 Accepted."
    ),
)
async def save_memory(payload: SaveMemoryInput, db: Session = Depends(get_db)) -> SaveMemoryResult:
    ingest_req = IngestRequest(
        source=payload.source,
        workspace_id=payload.workspace_id,
        content=payload.content,
        provenance=payload.provenance,
    )
    result: IngestResponse = await ingest_memory(ingest_req, db)
    return SaveMemoryResult(
        status=result.status,
        session_id=result.session_id,
        workspace_id=result.workspace_id,
        source=result.source,
        processor_dispatch=result.processor_dispatch,
    )


# ── search_memory ──────────────────────────────────────────────────────────

class SearchMemoryResult(BaseModel):
    """Response returned to the MCP caller."""
    query: str
    limit: int
    workspace_id: str
    results: list[dict[str, Any]]


@router.get(
    "/search_memory",
    response_model=SearchMemoryResult,
    summary="Search memories (MCP tool)",
    description=(
        "MCP tool called by Copilot or Claude Desktop to retrieve relevant "
        "approved memories before starting work. Only status=approved memories "
        "are returned — pending_review and archived are never exposed."
    ),
)
async def search_memory(
    query: str = Query(..., min_length=1, description="What to look for"),
    limit: int = Query(5, ge=1, le=25, description="Max results"),
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SearchMemoryResult:
    resp: SearchResponse = await _search_memory(
        query=query,
        limit=limit,
        workspace_id=workspace_id,
        db=db,
    )
    return SearchMemoryResult(
        query=resp.query,
        limit=resp.limit,
        workspace_id=resp.workspace_id,
        results=[r.model_dump() for r in resp.results],
    )
