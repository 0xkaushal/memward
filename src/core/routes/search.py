from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.db import Memory, get_db
from core.workspace import resolve_workspace_id

router = APIRouter(tags=["search"])


class SearchResult(BaseModel):
    """A single search result."""

    id: str
    content: str
    source: str
    category: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Search results response."""

    query: str
    limit: int
    workspace_id: str
    results: list[SearchResult]


@router.get("/search", response_model=SearchResponse)
async def search_memory(
    query: Optional[str] = Query(None, min_length=1, description="Search query string — omit to list all recent approved memories"),
    limit: int = Query(5, ge=1, le=25, description="Max results to return"),
    workspace_id: Optional[str] = Query(
        None, description="Workspace to search in (defaults to config WORKSPACE_ID)"
    ),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search approved memories for the workspace.

    Per AGENTS.md flow:
    1. Client calls GET /search?query=...
    2. FastAPI embeds the query (not done yet, uses keyword search for v1)
    3. pgvector similarity search filtered to status=approved AND workspace_id
    4. Return top-N matches

    If query is omitted, returns the most recent approved memories (used by
    the SessionStart hook to inject all known context at session start).

    IMPORTANT: Unreviewed memories (status != approved) never leak into results.
    """
    workspace_id = resolve_workspace_id(workspace_id)

    # For v1, simple keyword search on content
    # TODO: Implement embedding + pgvector similarity search
    base_q = db.query(Memory).filter(
        Memory.workspace_id == workspace_id,
        Memory.status == "approved",
    )
    if query:
        base_q = base_q.filter(Memory.content.ilike(f"%{query}%"))
    matches = base_q.order_by(Memory.created_at.desc()).limit(limit).all()

    results = [
        SearchResult(
            id=str(m.id),
            content=m.content,
            source=m.source,
            category=m.category,
            status=m.status,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in matches
    ]

    return SearchResponse(
        query=query or "",
        limit=limit,
        workspace_id=workspace_id,
        results=results,
    )
