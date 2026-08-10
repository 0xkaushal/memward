"""Tests for the auth seam in workspace.py.

Verifies that:
- When API_TOKEN is not set, all requests pass through (local dev mode).
- When token enforcement is active via dependency override, missing/wrong tokens get 401.
- When token enforcement is active, the correct token succeeds.

Uses FastAPI dependency overrides against the already-running session-scoped
client — avoids restarting the app (which breaks the MCP session manager singleton).
"""

import pytest
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional

from core.main import app
from core.workspace import verify_token

_SECRET = "test-secret-token"
_bearer = HTTPBearer(auto_error=False)


def _token_enforcer(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> None:
    """Drop-in replacement for verify_token that requires _SECRET."""
    if credentials is None or credentials.credentials != _SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@pytest.fixture(autouse=False)
def with_token_enforced():
    """Override verify_token to require the secret for the duration of a test."""
    app.dependency_overrides[verify_token] = _token_enforcer
    yield
    app.dependency_overrides.pop(verify_token, None)


def test_no_token_configured_allows_all_requests(client):
    """Default test client has API_TOKEN='' so all requests pass through."""
    r = client.post("/ingest", json={"source": "copilot", "content": "auth test"})
    assert r.status_code == 202


def test_token_required_missing_header(client, with_token_enforced):
    """When token enforcement is active, a request with no header gets 401."""
    r = client.post("/ingest", json={"source": "copilot", "content": "auth test"})
    assert r.status_code == 401


def test_token_required_wrong_token(client, with_token_enforced):
    """When token enforcement is active, a wrong token gets 401."""
    r = client.post(
        "/ingest",
        json={"source": "copilot", "content": "auth test"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_token_required_correct_token(client, with_token_enforced):
    """When token enforcement is active, the correct token succeeds."""
    r = client.post(
        "/ingest",
        json={"source": "copilot", "content": "auth test"},
        headers={"Authorization": f"Bearer {_SECRET}"},
    )
    assert r.status_code == 202


def test_search_also_protected(client, with_token_enforced):
    """Token enforcement applies to /search as well as /ingest."""
    assert client.get("/search").status_code == 401
    assert (
        client.get("/search", headers={"Authorization": f"Bearer {_SECRET}"}).status_code
        == 200
    )
