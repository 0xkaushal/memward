"""Database models and connection management."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import uuid

from core.config import settings

Base = declarative_base()


def _new_uuid() -> str:
    """Generate a new UUID as a string (works on Postgres and SQLite)."""
    return str(uuid.uuid4())


class Memory(Base):
    """Extracted memory with human-curated review gate."""

    __tablename__ = "memories"

    id = Column(
        String(36),
        primary_key=True,
        default=_new_uuid,
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
    embedding = Column(Text, nullable=True)  # JSON array string from embedding model
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


class Collection(Base):
    """User-created container for grouping memories."""

    __tablename__ = "collections"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=_new_uuid, nullable=False)
    workspace_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    color = Column(String(32), nullable=True)   # e.g. "#6366f1"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    memberships = relationship("MemoryCollection", back_populates="collection", cascade="all, delete-orphan")


class MemoryCollection(Base):
    """Join table: many memories ↔ many collections."""

    __tablename__ = "memory_collections"
    __table_args__ = (UniqueConstraint("memory_id", "collection_id", name="uq_memory_collection"),)

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=_new_uuid, nullable=False)
    memory_id = Column(PG_UUID(as_uuid=False), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(PG_UUID(as_uuid=False), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    collection = relationship("Collection", back_populates="memberships")


class RawSession(Base):
    """Raw session archive for re-processing without re-capturing."""

    __tablename__ = "raw_sessions"

    id = Column(
        String(36),
        primary_key=True,
        default=_new_uuid,
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
