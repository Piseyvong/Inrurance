"""Application configuration loaded from environment variables.

The module centralises settings that affect storage, upload validation, OCR,
and Azure OpenAI extraction. No secrets are hardcoded; production deployments
should provide credentials through environment variables.
"""

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime settings for the claims verification API.

    Inputs come from environment variables. Outputs are typed attributes used
    by routers and services. Upload limits and paths are configurable so tests
    and deployments do not need to patch business logic.
    """

    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    database_url: str | None = os.getenv("DATABASE_URL")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_db: str = os.getenv("POSTGRES_DB", "insurance_claims_demo")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))
    processed_dir: Path = Path(os.getenv("PROCESSED_DIR", "processed_uploads"))
    processing_log_path: Path = Path(os.getenv("PROCESSING_LOG_PATH", "logs/processing_results.jsonl"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

    ocr_provider: str = os.getenv("OCR_PROVIDER", "kiri")

    # Accept both the application's original variable names and the Azure
    # Foundry names shown in the portal. Secrets stay in the environment only.
    azure_openai_endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_PROJECT_ENDPOINT")
    azure_openai_api_key: str | None = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
    azure_openai_deployment: str | None = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("AZURE_OPENAI_MODEL")

    llm_request_timeout_seconds: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "20"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    company_name: str = os.getenv("COMPANY_NAME", "Insurance AI")
    consultation_phone: str | None = os.getenv("CONSULTATION_PHONE")
    consultation_email: str | None = os.getenv("CONSULTATION_EMAIL")
    office_hours: str | None = os.getenv("OFFICE_HOURS")
    office_location: str | None = os.getenv("OFFICE_LOCATION")

    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175").split(",")
        if origin.strip()
    ]

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return a SQLAlchemy-compatible PostgreSQL URL."""

        if self.database_url:
            return self.database_url
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for dependency injection and services."""

    return Settings()
