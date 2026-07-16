"""
Shared pytest fixtures.

Uses an in-memory SQLite database so tests run without any Supabase or
real Postgres connection — safe for CI with no secrets required.
"""

import os

# Set env vars BEFORE importing anything from the app so pydantic-settings
# picks them up.
os.environ.setdefault("SUPABASE_DB_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("LLM_API_KEY", "test-llm-key")
os.environ.setdefault("WORKSPACE_ID", "test-workspace")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.db import Base, get_db
from core.main import app

# ── In-memory SQLite engine ───────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

Base.metadata.create_all(bind=engine)

# Exported so test helpers can use it directly without circular imports
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def client():
    """Return one process-lifetime TestClient with the DB dependency overridden."""
    with TestClient(app) as c:
        yield c
