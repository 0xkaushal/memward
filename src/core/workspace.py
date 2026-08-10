"""Workspace identity boundary.

The application is single-workspace in v1, but every request must be resolved
through this one module so replacing it with verified auth later is local.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

_bearer = HTTPBearer(auto_error=False)


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> None:
    """Validate the Bearer token on every protected route.

    If API_TOKEN is not configured (local dev default), all requests pass
    through unchecked. In production, set API_TOKEN in the environment and
    every request must supply a matching Authorization: Bearer <token> header.

    This is the single place to swap in JWT verification or Cognito/OAuth
    later — no other module should inspect auth headers.
    """
    if not settings.API_TOKEN:
        return  # auth not configured — open for local dev
    if credentials is None or credentials.credentials != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
