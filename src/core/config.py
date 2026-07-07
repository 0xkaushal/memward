import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

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
        os.getenv("PROCESSOR_TIMEOUT_SECONDS", "3.0")
    )

    # LLM provider configuration (provider-agnostic)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", None)

    # Backward compatibility with older env key name.
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)

    # App
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def get_llm_api_key() -> Optional[str]:
    """Resolve the configured LLM API key with backward compatibility."""
    return settings.LLM_API_KEY or settings.ANTHROPIC_API_KEY
