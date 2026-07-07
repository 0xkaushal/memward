from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    source: str = Field(..., examples=["copilot"])
    workspace_id: str = Field(..., examples=["default-workspace"])
    content: str = Field(..., examples=["User decided to use Supabase with pgvector."])


@router.post("/ingest", status_code=202)
async def ingest_memory(payload: IngestRequest) -> dict[str, str]:
    return {
        "status": "accepted",
        "source": payload.source,
        "workspace_id": payload.workspace_id,
    }