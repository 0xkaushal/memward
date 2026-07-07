from typing import Optional

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
    - Call Anthropic API to extract facts + assign category
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

    # TODO: Queue to SQS for async processing
    # sqs_client.send_message(
    #     QueueUrl=settings.AWS_SQS_QUEUE_URL,
    #     MessageBody=json.dumps({
    #         "raw_session_id": str(raw_session.id),
    #         "workspace_id": workspace_id,
    #         "source": payload.source,
    #     }),
    # )

    return IngestResponse(
        status="accepted",
        session_id=str(raw_session.id),
        workspace_id=workspace_id,
        source=payload.source,
    )