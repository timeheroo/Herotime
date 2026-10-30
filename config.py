
"""Application configuration loaded from environment variables."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    BOT_TOKEN: str = Field(min_length=1)
    DATABASE_URL: str = Field(min_length=1)
    OWNER_ID: int = Field(gt=0)

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("BOT_TOKEN cannot be empty")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("DATABASE_URL cannot be empty")

        if value.startswith("postgres://"):
            value = value.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )
        elif value.startswith("postgresql://"):
            value = value.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )

        return value


settings = Settings()

BOT_TOKEN = settings.BOT_TOKEN
DATABASE_URL = settings.DATABASE_URL
OWNER_ID = settings.OWNER_ID
