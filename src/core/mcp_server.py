"""Real Streamable HTTP MCP surface for Copilot and other MCP clients."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from core import db as db_module
from core.db import Memory
from core.ingestion import create_raw_session
from core.workspace import current_workspace_id

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


@mcp.tool()
def save_memory(
    content: str,
    source: str = "copilot",
    provenance: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Save a concise candidate memory for human review."""
    if source not in {"claude_code", "copilot", "claude_desktop", "opencode", "internal_chatbot_x"}:
        raise ValueError("Unsupported source")
    db = _session()
    try:
        raw_session, created = create_raw_session(
            db,
            source=source,
            workspace_id=current_workspace_id(),
            content=content,
            provenance=provenance,
        )
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
        q = db.query(Memory).filter(
            Memory.workspace_id == current_workspace_id(),
            Memory.status == "approved",
        )
        # Only apply text filter when the query is a specific term, not a
        # natural-language question. Fall back to returning all approved
        # memories when no keyword match is possible — the LLM can reason
        # over them. Vector similarity search is the v2 upgrade path.
        if query.strip():
            q = q.filter(Memory.content.ilike(f"%{query}%"))
        rows = q.order_by(Memory.created_at.desc()).limit(max(1, min(limit, 25))).all()
        # If keyword filter returned nothing, return all approved memories so
        # the LLM always has full context rather than a false empty result.
        if not rows and query.strip():
            rows = (
                db.query(Memory)
                .filter(
                    Memory.workspace_id == current_workspace_id(),
                    Memory.status == "approved",
                )
                .order_by(Memory.created_at.desc())
                .limit(max(1, min(limit, 25)))
                .all()
            )
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
