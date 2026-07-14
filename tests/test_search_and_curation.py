"""Tests for GET /search and curation routes."""

import uuid
from datetime import datetime

from core.db import Memory


def _seed_approved_memory(content="approved memory content"):
    """Directly insert an approved Memory row into the test DB."""
    # Import from conftest module directly (not as a package) to avoid
    # 'No module named tests' when pythonpath only includes src/
    import importlib, sys
    conftest = sys.modules.get("conftest") or importlib.import_module("conftest")
    TestingSessionLocal = conftest.TestingSessionLocal

    db = TestingSessionLocal()
    try:
        mem_id = str(uuid.uuid4())
        m = Memory(
            id=mem_id,
            workspace_id="test-workspace",
            source="copilot",
            category="code",
            content=content,
            status="approved",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(m)
        db.commit()
        # Return the UUID object (not string) so SQLite UUID column works correctly
        return mem_id
    finally:
        db.close()


# ── Search ────────────────────────────────────────────────────────────────────

def test_search_empty_returns_200(client):
    r = client.get("/search")
    assert r.status_code == 200
    assert "results" in r.json()


def test_search_only_returns_approved(client):
    _seed_approved_memory(content="vector search with pgvector")
    r = client.get("/search?query=pgvector")
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert result["status"] == "approved"


def test_search_no_match_returns_empty(client):
    r = client.get("/search?query=zzznomatch999")
    assert r.status_code == 200
    assert r.json()["results"] == []


# ── Curation ──────────────────────────────────────────────────────────────────

def test_curation_list_returns_200(client):
    r = client.get("/curation/memories")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "total" in data


def test_curation_approve_memory(client):
    memory_id = _seed_approved_memory(content="use black for formatting")
    r = client.patch(f"/curation/memories/{memory_id}", json={"status": "pending_review"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"

    r = client.patch(f"/curation/memories/{memory_id}", json={"status": "approved"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_curation_edit_content(client):
    memory_id = _seed_approved_memory(content="original content")
    r = client.patch(f"/curation/memories/{memory_id}", json={"content": "updated content"})
    assert r.status_code == 200
    assert r.json()["content"] == "updated content"


def test_curation_delete_memory(client):
    memory_id = _seed_approved_memory(content="to be deleted")
    r = client.delete(f"/curation/memories/{memory_id}")
    assert r.status_code == 204

    ids = [m["id"] for m in client.get("/curation/memories").json()["results"]]
    assert str(memory_id) not in ids


def test_curation_invalid_status_rejected(client):
    memory_id = _seed_approved_memory(content="status test")
    r = client.patch(f"/curation/memories/{memory_id}", json={"status": "invalid_status"})
    assert r.status_code == 400


def test_curation_patch_nonexistent_returns_404(client):
    r = client.patch(f"/curation/memories/{uuid.uuid4()}", json={"status": "approved"})
    assert r.status_code == 404


def test_curation_delete_nonexistent_returns_404(client):
    r = client.delete(f"/curation/memories/{uuid.uuid4()}")
    assert r.status_code == 404
