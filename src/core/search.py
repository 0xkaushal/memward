"""Shared similarity search logic for approved memories.

Both the MCP tool (mcp_server.py) and the HTTP route (routes/search.py)
use this module so the upgrade from keyword to vector search is one change.

Search strategy (in priority order):
1. Vector cosine similarity — if pgvector is available and the memory has
   an embedding, use cosine distance ordering.
2. Keyword fallback — ilike on content for memories without embeddings, or
   when pgvector is unavailable.
3. Recent approved listing — if no query is provided, return recent approved
   memories for connector injection and review surfaces.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.db import Memory
from core.config import settings, get_llm_api_key

logger = logging.getLogger(__name__)

# Embedding dimensions for text-embedding-3-small
_EMBED_DIMS = 1536


def _embed_query(query: str) -> list[float] | None:
    """Embed the search query using the same model as the processor.

    Returns None if the LLM client is not configured (graceful degradation
    to keyword search).
    """
    api_key = get_llm_api_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=settings.LLM_BASE_URL)
        resp = client.embeddings.create(
            model=settings.LLM_EMBEDDING_MODEL,
            input=query[:8000],
        )
        return resp.data[0].embedding
    except Exception as exc:
        logger.warning("Embedding query failed, falling back to keyword search: %s", exc)
        return None


def search_approved_memories(
    db: Session,
    query: str,
    workspace_id: str,
    limit: int = 5,
) -> list[Any]:
    """Return approved memories ranked by relevance to query.

    Tries vector cosine similarity first; falls back to keyword search.
    If no query is provided, returns the most recent approved memories.
    """
    limit = max(1, min(limit, 25))
    base_filter = [
        Memory.workspace_id == workspace_id,
        Memory.status == "approved",
    ]

    query_text = query.strip()

    # --- 1. Vector similarity search ---
    if query_text and settings.MEMWARD_MODE != "local":
        query_vec = _embed_query(query)
        if query_vec is not None:
            try:
                from pgvector.sqlalchemy import Vector  # noqa: F401
                rows = (
                    db.query(Memory)
                    .filter(*base_filter, Memory.embedding.isnot(None))
                    .order_by(Memory.embedding.cosine_distance(query_vec))
                    .limit(limit)
                    .all()
                )
                if rows:
                    return rows
                # Vector search returned nothing (no embeddings yet); fall through
            except Exception as exc:
                logger.warning("Vector search failed, falling back to keyword: %s", exc)
                db.rollback()  # Clear the failed transaction so fallback queries can run

    # --- 2. Keyword fallback ---
    if query_text:
        keyword_pattern = f"%{query_text}%"
        if settings.MEMWARD_MODE == "local":
            rows = (
                db.query(Memory)
                .filter(*base_filter, func.lower(Memory.content).like(func.lower(keyword_pattern)))
                .order_by(Memory.created_at.desc())
                .limit(limit)
                .all()
            )
        else:
            rows = (
                db.query(Memory)
                .filter(*base_filter, Memory.content.ilike(keyword_pattern))
                .order_by(Memory.created_at.desc())
                .limit(limit)
                .all()
            )
        if rows:
            return rows

    if query_text:
        return []

    # --- 3. Recent approved listing (used when query is omitted) ---
    return (
        db.query(Memory)
        .filter(*base_filter)
        .order_by(Memory.created_at.desc())
        .limit(limit)
        .all()
    )
