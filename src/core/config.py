import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    MEMWARD_MODE: str = os.getenv("MEMWARD_MODE", "local").lower()
    MEMWARD_HOME: str = os.getenv("MEMWARD_HOME", str(Path.home() / ".memward"))
    MEMWARD_LOCAL_DB_PATH: Optional[str] = os.getenv("MEMWARD_LOCAL_DB_PATH", None)

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_DB_URL: Optional[str] = os.getenv("SUPABASE_DB_URL", None)

    # Workspace (single workspace for v1)
    WORKSPACE_ID: str = os.getenv("WORKSPACE_ID", "default-workspace")

    # S3 (for raw session archival)
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET", None)
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # SQS (for async processing)
    AWS_SQS_QUEUE_URL: Optional[str] = os.getenv("AWS_SQS_QUEUE_URL", None)

    # Processor API (POC)
    PROCESSOR_API_URL: str = os.getenv("PROCESSOR_API_URL", "http://127.0.0.1:8010")
    PROCESSOR_TIMEOUT_SECONDS: float = float(
        os.getenv("PROCESSOR_TIMEOUT_SECONDS", "30.0")
    )

    # LLM provider configuration (OpenRouter or any OpenAI-compatible endpoint)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", None)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_CHAT_MODEL: str = os.getenv("LLM_CHAT_MODEL", "openai/gpt-4o-mini")
    LLM_EMBEDDING_MODEL: str = os.getenv("LLM_EMBEDDING_MODEL", "openai/text-embedding-3-small")

    # Backward compatibility with older env key name.
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)

    # Auth — bearer token for all API routes (optional in local dev; set in prod)
    API_TOKEN: Optional[str] = os.getenv("API_TOKEN", None)

    # App
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()


def get_llm_api_key() -> Optional[str]:
    """Resolve the configured LLM API key with backward compatibility."""
    return settings.LLM_API_KEY or settings.ANTHROPIC_API_KEY


def get_memward_home() -> Path:
    """Return the memward home directory used for local state."""
    return Path(settings.MEMWARD_HOME).expanduser()


def get_local_db_path() -> Path:
    """Return the SQLite path for local mode."""
    if settings.MEMWARD_LOCAL_DB_PATH:
        if settings.MEMWARD_LOCAL_DB_PATH == ":memory:":
            return Path(":memory:")
        return Path(settings.MEMWARD_LOCAL_DB_PATH).expanduser()
    return get_memward_home() / "memward.db"
