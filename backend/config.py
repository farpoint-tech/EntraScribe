from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure / Microsoft Graph
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str

    # AI providers — all optional; at least one must be set at runtime
    groq_api_key: str = ""
    gemini_api_key: str = ""
    mistral_api_key: str = ""

    # App
    allowed_origins: str = "http://localhost:3000"
    secret_key: str
    dry_run: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
