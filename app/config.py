from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./snapkey.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-secret-change-me-please"
    credential_encryption_key: str = ""
    access_token_expire_minutes: int = 60
    task_always_eager: bool = False
    llm_provider: str = "deterministic"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_max_steps: int = 6
    openrouter_site_url: str = ""
    openrouter_app_name: str = "Snapkey Assistant"
    concierge_mode: bool = False
    telegram_bot_token: str = ""
    telegram_operator_chat_id: str = ""
    telegram_webhook_secret: str = ""
    upload_dir: str = "uploads"
    max_upload_bytes: int = 15_000_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
