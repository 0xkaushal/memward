"""Tests for root and health routes."""


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "memward"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
