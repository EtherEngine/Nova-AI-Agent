"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseModel):
    """Runtime configuration for the agent service.

    The OpenAI API key is read from the environment and never logged or
    exposed to clients.
    """

    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(min_length=1)
    openai_timeout_seconds: float = Field(default=30.0, gt=0)
    openai_max_retries: int = Field(default=2, ge=0)
    max_tool_rounds: int = Field(default=5, ge=1, le=20)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    # Optional async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host/db.
    # When unset the app still runs; database-backed features are disabled.
    database_url: str | None = None
    # Optional JWT signing secret. When unset, authentication is disabled.
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)
    # Retrieval-Augmented Generation (RAG) / embeddings.
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, gt=0)
    rag_top_k: int = Field(default=4, ge=1, le=50)
    max_upload_mb: int = Field(default=10, ge=1, le=100)
    upload_dir: str = "./data/uploads"

    @classmethod
    def load(cls) -> Settings:
        """Load and validate settings from the environment.

        Raises:
            ConfigError: If required values are missing or invalid.
        """
        load_dotenv()

        cors_raw = os.getenv("CORS_ORIGINS", "").strip()
        cors_origins = (
            [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
            if cors_raw
            else ["http://localhost:5173", "http://127.0.0.1:5173"]
        )

        raw = {
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "openai_model": os.getenv("OPENAI_MODEL", ""),
            "openai_timeout_seconds": os.getenv("OPENAI_TIMEOUT_SECONDS", "30"),
            "openai_max_retries": os.getenv("OPENAI_MAX_RETRIES", "2"),
            "max_tool_rounds": os.getenv("MAX_TOOL_ROUNDS", "5"),
            "cors_origins": cors_origins,
            "database_url": os.getenv("DATABASE_URL") or None,
            "jwt_secret_key": os.getenv("JWT_SECRET_KEY") or None,
            "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
            "access_token_expire_minutes": os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"),
            "refresh_token_expire_days": os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            "embedding_dim": os.getenv("EMBEDDING_DIM", "1536"),
            "rag_top_k": os.getenv("RAG_TOP_K", "4"),
            "max_upload_mb": os.getenv("MAX_UPLOAD_MB", "10"),
            "upload_dir": os.getenv("UPLOAD_DIR", "./data/uploads"),
        }

        missing = [
            env_name
            for env_name, key in (
                ("OPENAI_API_KEY", "openai_api_key"),
                ("OPENAI_MODEL", "openai_model"),
            )
            if not raw[key]
        ]
        if missing:
            raise ConfigError(
                "Fehlende erforderliche Konfiguration: "
                + ", ".join(missing)
                + ". Bitte in der .env-Datei oder als Umgebungsvariable setzen."
            )

        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            # Do not leak secret values; only surface which fields failed.
            fields = ", ".join(str(err["loc"][0]) for err in exc.errors())
            raise ConfigError(
                f"Ungültige Konfigurationswerte für: {fields}."
            ) from exc
