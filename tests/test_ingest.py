"""Tests for POST /ingest."""


def test_ingest_returns_202(client):
    r = client.post(
        "/ingest",
        json={"source": "copilot", "content": "preferred language is Python"},
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "accepted"
    assert data["source"] == "copilot"
    assert data["workspace_id"] == "test-workspace"
    assert "session_id" in data
    # processor is not running in tests — dispatch will be "failed" or "skipped"
    assert data["processor_dispatch"] in ("accepted", "failed", "skipped")


def test_ingest_invalid_source(client):
    r = client.post(
        "/ingest",
        json={"source": "unknown_tool", "content": "some content"},
    )
    assert r.status_code == 400
    assert "Invalid source" in r.json()["detail"]


def test_ingest_empty_content_rejected(client):
    r = client.post(
        "/ingest",
        json={"source": "copilot", "content": ""},
    )
    assert r.status_code == 422  # pydantic min_length=1


def test_ingest_custom_workspace(client):
    r = client.post(
        "/ingest",
        json={
            "source": "claude_code",
            "content": "use sqlalchemy for ORM",
            "workspace_id": "my-org",
        },
    )
    assert r.status_code == 202
    assert r.json()["workspace_id"] == "my-org"


def test_ingest_all_valid_sources(client):
    for source in ["claude_code", "copilot", "claude_desktop", "internal_chatbot_x"]:
        r = client.post(
            "/ingest",
            json={"source": source, "content": f"test from {source}"},
        )
        assert r.status_code == 202, f"expected 202 for source={source}"
