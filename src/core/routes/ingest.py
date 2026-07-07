from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.db import RawSession, get_db

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
    processor_dispatch: str = Field(
        ..., description="Best-effort processor dispatch status"
    )


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
    workspace_id = payload.workspace_id or settings.WORKSPACE_ID

    # Validate source
    valid_sources = ["claude_code", "copilot", "claude_desktop", "internal_chatbot_x"]
    if payload.source not in valid_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source. Must be one of {valid_sources}",
        )

    # Store raw session
    raw_session = RawSession(
        workspace_id=workspace_id,
        source=payload.source,
        content=payload.content,
        s3_key=None,  # Would be set by async Lambda
    )
    db.add(raw_session)
    db.commit()
    db.refresh(raw_session)

    processor_dispatch = "skipped"

    # POC: call processor API over HTTP. This is best-effort and non-blocking
    # for ingestion success (ingest still returns 202 when raw session is saved).
    process_payload = {
        "raw_session_id": str(raw_session.id),
        "workspace_id": workspace_id,
        "source": payload.source,
        "content": payload.content,
        "provenance": payload.provenance,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.PROCESSOR_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{settings.PROCESSOR_API_URL}/process-memory",
                json=process_payload,
            )
            processor_dispatch = "accepted" if resp.status_code == 202 else "failed"
    except Exception:
        processor_dispatch = "failed"

    return IngestResponse(
        status="accepted",
        session_id=str(raw_session.id),
        workspace_id=workspace_id,
        source=payload.source,
        processor_dispatch=processor_dispatch,
    )