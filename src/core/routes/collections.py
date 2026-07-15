"""Collection CRUD routes — user-created containers for grouping memories."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.db import Collection, Memory, MemoryCollection, get_db

router = APIRouter(prefix="/curation/collections", tags=["collections"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CollectionOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    color: Optional[str] = None
    memory_count: int = 0
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    results: list[CollectionOut]


class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    color: Optional[str] = Field(None, max_length=32)


class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    color: Optional[str] = Field(None, max_length=32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_out(c: Collection, db: Session) -> CollectionOut:
    count = db.query(MemoryCollection).filter(MemoryCollection.collection_id == c.id).count()
    return CollectionOut(
        id=str(c.id),
        workspace_id=c.workspace_id,
        name=c.name,
        color=c.color,
        memory_count=count,
        created_at=c.created_at.isoformat() if c.created_at else "",
        updated_at=c.updated_at.isoformat() if c.updated_at else "",
    )


# ── Collection CRUD ───────────────────────────────────────────────────────────

@router.get("", response_model=CollectionListResponse)
async def list_collections(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> CollectionListResponse:
    ws = workspace_id or settings.WORKSPACE_ID
    rows = db.query(Collection).filter(Collection.workspace_id == ws).order_by(Collection.created_at.asc()).all()
    return CollectionListResponse(results=[_to_out(c, db) for c in rows])


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(
    body: CreateCollectionRequest,
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> CollectionOut:
    ws = workspace_id or settings.WORKSPACE_ID
    c = Collection(workspace_id=ws, name=body.name.strip(), color=body.color)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c, db)


@router.patch("/{collection_id}", response_model=CollectionOut)
async def update_collection(
    collection_id: str,
    body: UpdateCollectionRequest,
    db: Session = Depends(get_db),
) -> CollectionOut:
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    if body.name is not None:
        c.name = body.name.strip()
    if body.color is not None:
        c.color = body.color
    db.commit()
    db.refresh(c)
    return _to_out(c, db)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, db: Session = Depends(get_db)) -> None:
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Collection not found")
    db.delete(c)
    db.commit()


# ── Membership ────────────────────────────────────────────────────────────────

@router.put("/{collection_id}/memories/{memory_id}", status_code=204)
async def add_memory_to_collection(
    collection_id: str,
    memory_id: str,
    db: Session = Depends(get_db),
) -> None:
    if not db.query(Collection).filter(Collection.id == collection_id).first():
        raise HTTPException(status_code=404, detail="Collection not found")
    if not db.query(Memory).filter(Memory.id == memory_id).first():
        raise HTTPException(status_code=404, detail="Memory not found")
    existing = db.query(MemoryCollection).filter(
        MemoryCollection.memory_id == memory_id,
        MemoryCollection.collection_id == collection_id,
    ).first()
    if not existing:
        db.add(MemoryCollection(memory_id=memory_id, collection_id=collection_id))
        db.commit()


@router.delete("/{collection_id}/memories/{memory_id}", status_code=204)
async def remove_memory_from_collection(
    collection_id: str,
    memory_id: str,
    db: Session = Depends(get_db),
) -> None:
    row = db.query(MemoryCollection).filter(
        MemoryCollection.memory_id == memory_id,
        MemoryCollection.collection_id == collection_id,
    ).first()
    if row:
        db.delete(row)
        db.commit()
