"""Curation routes — list, approve, archive, and delete memories.

These are the backend endpoints for the human review gate. Only approved
memories feed into search; pending_review and archived never leak out.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.db import Memory, MemoryCollection, get_db

router = APIRouter(prefix="/curation", tags=["curation"])

_VALID_STATUSES = ("pending_review", "approved", "archived")


class MemoryOut(BaseModel):
    id: str
    workspace_id: str
    source: str
    category: str
    content: str
    status: str
    collection_ids: list[str] = []
    provenance: Optional[dict] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MemoryListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    results: list[MemoryOut]


class PatchMemoryRequest(BaseModel):
    status: Optional[str] = None
    content: Optional[str] = None


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> MemoryListResponse:
    """List all memories, optionally filtered. No status restriction — shows pending_review too."""
    ws = workspace_id or settings.WORKSPACE_ID
    q = db.query(Memory).filter(Memory.workspace_id == ws)

    if status_filter:
        q = q.filter(Memory.status == status_filter)
    if category:
        q = q.filter(Memory.category == category)
    if source:
        q = q.filter(Memory.source == source)

    total = q.count()
    rows = q.order_by(Memory.created_at.desc()).offset(offset).limit(limit).all()

    return MemoryListResponse(
        total=total,
        offset=offset,
        limit=limit,
        results=[_to_out(m, db) for m in rows],
    )


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
async def patch_memory(
    memory_id: str,
    body: PatchMemoryRequest,
    db: Session = Depends(get_db),
) -> MemoryOut:
    """Update status and/or content of a memory."""
    m = db.query(Memory).filter(Memory.id == memory_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Memory not found")

    if body.status is not None:
        if body.status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of {_VALID_STATUSES}",
            )
        m.status = body.status

    if body.content is not None:
        if not body.content.strip():
            raise HTTPException(status_code=400, detail="content must not be empty")
        m.content = body.content.strip()

    db.commit()
    db.refresh(m)
    return _to_out(m, db)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Permanently delete a memory row."""
    m = db.query(Memory).filter(Memory.id == memory_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(m)
    db.commit()


def _to_out(m: Memory, db: Session) -> MemoryOut:
    collection_ids = [
        str(mc.collection_id)
        for mc in db.query(MemoryCollection).filter(MemoryCollection.memory_id == m.id).all()
    ]
    return MemoryOut(
        id=str(m.id),
        workspace_id=m.workspace_id,
        source=m.source,
        category=m.category,
        content=m.content,
        status=m.status,
        collection_ids=collection_ids,
        provenance=m.provenance,
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else "",
    )
