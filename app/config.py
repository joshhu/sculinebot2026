from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    line_channel_access_token: str
    line_channel_secret: str

    gemini_api_key: str
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"

    supabase_url: str
    supabase_service_role_key: str

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
