from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    line_channel_access_token: str
    line_channel_secret: str

    gemini_api_key: str
    # 3.1 沒有「非 lite」的 flash；flash-lite-preview 即為 3.1 flash 本體
    gemini_model_fast: str = "gemini-3.1-flash-lite-preview"
    gemini_model_pro: str = "gemini-3.1-pro-preview"

    supabase_url: str
    supabase_service_role_key: str

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
