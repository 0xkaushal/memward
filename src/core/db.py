"""Database models and connection management."""
from datetime import datetime, timezone
import json

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Integer,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import uuid

from pgvector.sqlalchemy import Vector

from core.config import get_local_db_path, get_memward_home, settings

Base = declarative_base()


class EmbeddingType(TypeDecorator):
    """Store pgvector on Postgres and JSON-encoded vectors on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(1536))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value

    def process_result_value(self, value, dialect):
        return value


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
            "opencode",
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
    embedding = Column(EmbeddingType(), nullable=True)  # pgvector on Postgres, JSON on SQLite
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
    raw_session_id = Column(PG_UUID(as_uuid=False), nullable=True, index=True)
    candidate_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Collection(Base):
    """User-created container for grouping memories."""

    __tablename__ = "collections"

    id = Column(String(36), primary_key=True, default=_new_uuid, nullable=False)
    workspace_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    color = Column(String(32), nullable=True)   # e.g. "#6366f1"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    memberships = relationship("MemoryCollection", back_populates="collection", cascade="all, delete-orphan")


class MemoryCollection(Base):
    """Join table: many memories ↔ many collections."""

    __tablename__ = "memory_collections"
    __table_args__ = (UniqueConstraint("memory_id", "collection_id", name="uq_memory_collection"),)

    id = Column(String(36), primary_key=True, default=_new_uuid, nullable=False)
    memory_id = Column(String(36), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    collection = relationship("Collection", back_populates="memberships")


class RawSession(Base):
    """Raw session archive for re-processing without re-capturing."""

    __tablename__ = "raw_sessions"

    id = Column(
        PG_UUID(as_uuid=False),
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
            "opencode",
            "internal_chatbot_x",
            name="raw_source_type",
        ),
        nullable=False,
    )
    s3_key = Column(String(1024), nullable=True)  # Path in S3 bucket
    content = Column(Text, nullable=False)  # Raw payload for local dev
    provenance = Column(JSON, nullable=True)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
    processing_status = Column(String(32), nullable=False, default="pending", index=True)
    processing_attempts = Column(Integer, nullable=False, default=0)
    processing_error = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# Database connection setup
def get_db_url() -> str:
    """Get database URL from config, supporting local SQLite mode."""
    if settings.MEMWARD_MODE == "local":
        local_db_path = get_local_db_path()
        if str(local_db_path) == ":memory:":
            return "sqlite:///:memory:"
        local_db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{local_db_path}"
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
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite:///") else {}
    engine = create_engine(db_url, echo=settings.DEBUG, connect_args=connect_args)

    if settings.MEMWARD_MODE == "local":
        memward_home = get_memward_home()
        memward_home.mkdir(parents=True, exist_ok=True)
        (memward_home / "checkpoints").mkdir(parents=True, exist_ok=True)
        (memward_home / "logs").mkdir(parents=True, exist_ok=True)
    else:
        # Register pgvector type with every new psycopg2 connection.
        # This is a no-op if the vector extension is not yet enabled in the DB —
        # the server will still start and fall back to keyword search.
        from sqlalchemy import event
        from pgvector.psycopg2 import register_vector

        @event.listens_for(engine, "connect")
        def _register_vector(dbapi_conn, _):
            try:
                register_vector(dbapi_conn)
            except Exception:
                pass  # vector extension not yet installed; keyword fallback will be used

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
