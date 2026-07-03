import json
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_DEFAULT = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    # Look for .env in backend/ first, then fall back to repo root (../.env).
    # Later files in the tuple take precedence, so backend/.env overrides root.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database — Railway injects DATABASE_URL; individual vars used as fallback.
    postgres_db: str = "transferx"
    postgres_user: str = "transferx"
    postgres_password: str = "change-me"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        raw = os.environ.get("DATABASE_URL")
        if raw:
            # Railway uses postgres:// scheme; asyncpg requires postgresql+asyncpg://
            return raw.replace("postgres://", "postgresql+asyncpg://", 1).replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic migrations."""
        raw = os.environ.get("DATABASE_URL")
        if raw:
            return raw.replace("postgres://", "postgresql+psycopg2://", 1).replace(
                "postgresql://", "postgresql+psycopg2://", 1
            )
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Auth
    jwt_secret_key: str = _INSECURE_JWT_DEFAULT
    jwt_algorithm: str = "HS256"

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_must_be_changed(cls, v: str) -> str:
        if v == _INSECURE_JWT_DEFAULT:
            raise ValueError(
                "JWT_SECRET_KEY is still set to the insecure default. "
                "Set a secure random value in your .env file."
            )
        return v
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # CORS — accepts JSON array or comma-separated string; empty value uses dev defaults.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return v
        if not isinstance(v, str) or not v.strip():
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        v = v.strip()
        if v.startswith("["):
            return json.loads(v)
        # comma-separated: https://a.com,https://b.com
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    # Vendor / API-Sports
    apisports_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"

    # AI / LLM — set LLM_MODEL to the provider-prefixed model string, e.g.:
    #   "claude-sonnet-4-6"       (Anthropic)
    #   "gpt-4o"                  (OpenAI)
    #   "deepseek/deepseek-chat"  (DeepSeek)
    llm_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None

    # Feature flags
    transferx_enable_anti_sniping: bool = False
    transferx_sniping_window_minutes: int = 2
    transferx_sniping_extend_minutes: int = 2
    transferx_bid_rate: str = "10/m"

    # TRA-44: Email (SMTP) — leave smtp_host unset to disable email sending (dev/test default)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@transferx.local"
    smtp_from_name: str = "TransferX"
    smtp_use_tls: bool = True
    frontend_base_url: str = "http://localhost:5173"


settings = Settings()
