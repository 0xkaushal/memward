"""Database models and connection management."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid

from core.config import settings

Base = declarative_base()


class Memory(Base):
    """Extracted memory with human-curated review gate."""

    __tablename__ = "memories"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    workspace_id = Column(String(255), nullable=False, index=True)
    source = Column(
        Enum(
            "claude_code",
            "copilot",
            "claude_desktop",
            "internal_chatbot_x",
            name="source_type",
        ),
        nullable=False,
    )
    category = Column(
        Enum(
            "code",
            "project",
            "personal",
            "assistant_chat",
            name="category_type",
        ),
        nullable=False,
        default="personal",
    )
    content = Column(Text, nullable=False)
    embedding = Column(String(1024), nullable=True)  # pgvector stored as text in basic setup
    provenance = Column(JSON, nullable=True)  # {session_id, tool, timestamp, git_branch, git_repo}
    status = Column(
        Enum(
            "pending_review",
            "approved",
            "archived",
            name="status_type",
        ),
        nullable=False,
        default="pending_review",
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RawSession(Base):
    """Raw session archive for re-processing without re-capturing."""

    __tablename__ = "raw_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    workspace_id = Column(String(255), nullable=False, index=True)
    source = Column(
        Enum(
            "claude_code",
            "copilot",
            "claude_desktop",
            "internal_chatbot_x",
            name="raw_source_type",
        ),
        nullable=False,
    )
    s3_key = Column(String(1024), nullable=True)  # Path in S3 bucket
    content = Column(Text, nullable=False)  # Raw payload for local dev
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Database connection setup
def get_db_url() -> str:
    """Get database URL from config, preferring raw Postgres URL."""
    if settings.SUPABASE_DB_URL:
        return settings.SUPABASE_DB_URL
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        # Format: https://project-ref.supabase.co → postgresql://user:pass@project-ref.supabase.co/postgres
        # This is a placeholder; actual Supabase connection requires proper setup
        return ""
    return ""


engine = None
SessionLocal = None


def init_db() -> None:
    """Initialize database connection and create tables."""
    global engine, SessionLocal
    db_url = get_db_url()
    if not db_url:
        raise ValueError(
            "No database URL configured. Set SUPABASE_DB_URL or SUPABASE_URL + SUPABASE_KEY"
        )
    engine = create_engine(db_url, echo=settings.DEBUG)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database session."""
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
