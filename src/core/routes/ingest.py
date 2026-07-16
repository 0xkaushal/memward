import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.db import get_db
from core.ingestion import create_raw_session
from core.workspace import resolve_workspace_id

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    """Ingestion payload from MCP or webhook."""

    source: str = Field(
        ...,
        description="Source of the memory (claude_code, copilot, claude_desktop)",
        examples=["copilot"],
    )
    workspace_id: Optional[str] = Field(
        None,
        description="Workspace ID (defaults to WORKSPACE_ID from config)",
        examples=["default-workspace"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Raw session transcript or memory content",
        examples=["User decided to use Supabase with pgvector."],
    )
    provenance: Optional[dict] = Field(
        None,
        description="Optional metadata (session_id, timestamp, git_branch, etc.)",
    )


class IngestResponse(BaseModel):
    """Response after ingestion accepted."""

    status: str = Field("accepted", description="Always 'accepted' for 202")
    session_id: str = Field(..., description="UUID of the raw_sessions row")
    workspace_id: str = Field(..., description="Workspace that owns this session")
    source: str = Field(..., description="Source this came from")
    processor_dispatch: str = Field(..., description="Durable processing status")


@router.post("/ingest", status_code=202, response_model=IngestResponse)
async def ingest_memory(
    payload: IngestRequest, db: Session = Depends(get_db)
) -> IngestResponse:
    """
    Accept raw memory content and store it for async processing.

    Per AGENTS.md flow:
    1. FastAPI receives POST /ingest
    2. Store raw payload to raw_sessions table
    3. Drop message on SQS queue for async extraction (not done here yet)
    4. Return immediately with 202 Accepted

    Processing Lambda will:
    - Call the configured LLM provider API to extract facts + assign category
    - Write memories row with status=pending_review
    """
    workspace_id = resolve_workspace_id(payload.workspace_id)

    # Validate source
    valid_sources = ["claude_code", "copilot", "claude_desktop", "internal_chatbot_x"]
    if payload.source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source. Must be one of {valid_sources}",
        )

    raw_session, was_created = create_raw_session(
        db,
        source=payload.source,
        workspace_id=workspace_id,
        content=payload.content,
        provenance=payload.provenance,
    )

    # The raw session is the durable job record. A dispatch failure leaves it
    # pending for a worker/retry instead of silently dropping it.
    processor_dispatch = "queued" if was_created else "duplicate"

    # POC: call processor API over HTTP. This is best-effort and non-blocking
    # for ingestion success (ingest still returns 202 when raw session is saved).
    process_payload = {
        "raw_session_id": str(raw_session.id),
        "workspace_id": workspace_id,
        "source": payload.source,
    }

    if was_created:
        # Do not wait for LLM work before acknowledging an ingest. The processor
        # claims the persisted job and can be retried independently.
        asyncio.create_task(_dispatch_processor(process_payload))

    return IngestResponse(
        status="accepted",
        session_id=str(raw_session.id),
        workspace_id=workspace_id,
        source=payload.source,
        processor_dispatch=processor_dispatch,
    )


async def _dispatch_processor(payload: dict) -> None:
    """Nudge the v1 processor; the database job is the source of truth."""
    try:
        async with httpx.AsyncClient(timeout=settings.PROCESSOR_TIMEOUT_SECONDS) as client:
            await client.post(f"{settings.PROCESSOR_API_URL}/process-memory", json=payload)
    except Exception:
        # A worker or later retry will find the still-pending raw session.
        return
