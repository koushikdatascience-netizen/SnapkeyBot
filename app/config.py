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
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_output_format: str = "mp3_22050_32"
    elevenlabs_language_code: str = ""
    tts_max_characters: int = 5_000
    local_voice_enabled: bool = False
    local_stt_model: str = "small"
    local_stt_device: str = "cpu"
    local_stt_compute_type: str = "int8"
    local_stt_language: str = "hi"
    local_tts_provider: str = "sapi"
    local_tts_piper_executable: str = ""
    local_tts_piper_model: str = ""
    local_tts_sapi_voice: str = ""
    local_voice_silence_ms: int = 650
    local_voice_min_speech_ms: int = 350
    local_agent_enabled: bool = True
    local_agent_llm_base_url: str = ""
    local_agent_llm_model: str = ""
    local_agent_timeout_seconds: int = 20
    madhushala_exe_path: str = ""
    madhushala_process_name: str = "Madhushala Ultimate"
    desktop_apps_json: str = ""
    local_demo_meetings_json: str = ""
    cors_origins: str = ""
    public_url: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    youtube_api_key: str = ""
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""
    browserbase_region: str = "ap-southeast-1"
    report_database_url: str = ""
    report_connector_url: str = ""
    report_connector_secret: str = ""
    report_tenant_id: str = ""
    report_tenant_map_json: str = ""
    report_max_days: int = 90
    report_max_points: int = 50
    report_query_timeout_seconds: int = 8
    monitoring_camera_urls: str = ""
    monitoring_screen_url: str = ""
    demo_operator_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("report_database_url")
    @classmethod
    def normalize_report_database_url(cls, value: str) -> str:
        if value.startswith("mysql://"):
            return value.replace("mysql://", "mysql+asyncmy://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
