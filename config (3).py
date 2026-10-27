"""Application configuration loaded from environment variables.

Required environment variables:
- BOT_TOKEN: Telegram bot token from BotFather
- DATABASE_URL: Railway PostgreSQL connection URL
- OWNER_ID: Telegram numeric user ID of the project owner
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings for the Telegram management system."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    BOT_TOKEN: str = Field(min_length=1)
    DATABASE_URL: str = Field(min_length=1)
    OWNER_ID: int = Field(gt=0)

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Normalize Railway's PostgreSQL URL for async SQLAlchemy."""
        value = value.strip()
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


settings = Settings()

BOT_TOKEN = settings.BOT_TOKEN
DATABASE_URL = settings.DATABASE_URL
OWNER_ID = settings.OWNER_ID
