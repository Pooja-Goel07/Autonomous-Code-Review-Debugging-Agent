import pathlib
from typing import Optional

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path at module level to avoid Pydantic treating Path as a model field.
# config.py lives at backend/app/core/config.py — resolve() normalizes away any `.`
# segments Alembic injects via prepend_sys_path, then walk up 4 levels to project root
# (core → app → backend → project root) where .env lives.
_ENV_FILE = str(
    pathlib.Path(__file__).resolve().parent.parent.parent.parent / ".env"
)


class Settings(BaseSettings):
    # App Settings
    BACKEND_ENV: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    JWT_SECRET_KEY: str  # Required — no default. App fails to start if missing.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database Settings — password is required, never hardcoded
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str  # Required — no default. Must be set in .env.
    POSTGRES_DB: str = "code_review_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """Computed from individual POSTGRES_* fields — no hardcoded connection string."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # GitHub App Credentials
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None

    # GitHub OAuth Credentials
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: Optional[str] = None

    # LLM Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Frontend Settings
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
