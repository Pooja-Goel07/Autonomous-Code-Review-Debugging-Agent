import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    BACKEND_ENV: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    JWT_SECRET_KEY: str  # Required — no default. App will fail to start if not set in .env.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database Settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "code_review_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    # Default to asyncpg URL for async SQLAlchemy operations
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/code_review_db"

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

    # Settings configurations to automatically look for dotenv
    # __file__ = backend/app/core/config.py
    # Navigate up: core -> app -> backend -> project root (where .env lives)
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
