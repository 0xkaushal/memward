"""Durable ingestion helpers shared by HTTP and MCP entry points."""

import hashlib
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.db import RawSession


def ingestion_key(
    *, source: str, workspace_id: str, content: str, provenance: Optional[dict[str, Any]]
) -> str:
    """Create a stable key so replayed hooks and tool calls are safe."""
    payload = {
        "source": source,
        "workspace_id": workspace_id,
        "content": content,
        "provenance": provenance or {},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def create_raw_session(
    db: Session,
    *,
    source: str,
    workspace_id: str,
    content: str,
    provenance: Optional[dict[str, Any]],
) -> tuple[RawSession, bool]:
    """Persist an ingest exactly once and return ``(session, was_created)``."""
    key = ingestion_key(
        source=source,
        workspace_id=workspace_id,
        content=content,
        provenance=provenance,
    )
    existing = db.query(RawSession).filter(RawSession.idempotency_key == key).first()
    if existing:
        return existing, False

    raw_session = RawSession(
        workspace_id=workspace_id,
        source=source,
        content=content,
        provenance=provenance,
        idempotency_key=key,
        processing_status="pending",
    )
    db.add(raw_session)
    db.commit()
    db.refresh(raw_session)
    return raw_session, True
