"""Workspace identity boundary.

The application is single-workspace in v1, but every request must be resolved
through this one module so replacing it with verified auth later is local.
"""

from typing import Optional

from fastapi import HTTPException, status

from core.config import settings


def current_workspace_id() -> str:
    """Return the workspace resolved by the current v1 identity provider."""
    return settings.WORKSPACE_ID


def resolve_workspace_id(requested_workspace_id: Optional[str] = None) -> str:
    """Resolve and validate workspace scope without trusting a client override."""
    workspace_id = current_workspace_id()
    if requested_workspace_id is not None and requested_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested workspace is not available to this identity",
        )
    return workspace_id
