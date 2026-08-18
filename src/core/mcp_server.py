"""Real Streamable HTTP MCP surface for Copilot and other MCP clients."""

import asyncio
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from core import db as db_module
from core.config import settings
from core.ingestion import create_raw_session
from core.workspace import current_workspace_id
from core.search import search_approved_memories

mcp = FastMCP(
    "memward",
    instructions=(
        "Use search_memory before work when relevant. Save only concise facts, "
        "decisions, preferences, and constraints; saved memories require human review."
    ),
    stateless_http=True,
    streamable_http_path="/",
)


def _session():
    if db_module.SessionLocal is None:
        raise RuntimeError("Database is not initialized")
    return db_module.SessionLocal()


async def _dispatch_processor(payload: dict) -> None:
    """Fire-and-forget processor dispatch — same pattern as the /ingest route."""
    try:
        async with httpx.AsyncClient(timeout=settings.PROCESSOR_TIMEOUT_SECONDS) as client:
            await client.post(f"{settings.PROCESSOR_API_URL}/process-memory", json=payload)
    except Exception:
        # Raw session remains pending; process-pending will pick it up later.
        return


@mcp.tool()
def save_memory(
    content: str,
    source: str = "opencode",
    provenance: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Save a concise candidate memory for human review. Always pass source='opencode' when calling from OpenCode."""
    if source not in {"claude_code", "copilot", "claude_desktop", "opencode", "internal_chatbot_x"}:
        raise ValueError("Unsupported source")
    db = _session()
    try:
        workspace_id = current_workspace_id()
        raw_session, created = create_raw_session(
            db,
            source=source,
            workspace_id=workspace_id,
            content=content,
            provenance=provenance,
        )
        if created:
            payload = {
                "raw_session_id": str(raw_session.id),
                "workspace_id": workspace_id,
                "source": source,
            }
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(_dispatch_processor(payload))
            except RuntimeError:
                # No running event loop (e.g. sync context) — dispatch best-effort
                asyncio.run(_dispatch_processor(payload))
        return {
            "status": "queued" if created else "duplicate",
            "session_id": str(raw_session.id),
            "workspace_id": raw_session.workspace_id,
        }
    finally:
        db.close()


@mcp.tool()
def search_memory(query: str, limit: int = 5) -> dict[str, Any]:
    """Search only human-approved memories for the current workspace."""
    db = _session()
    try:
        rows = search_approved_memories(db, query=query, workspace_id=current_workspace_id(), limit=limit)
        return {
            "results": [
                {
                    "id": str(row.id),
                    "content": row.content,
                    "source": row.source,
                    "category": row.category,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]
        }
    finally:
        db.close()
