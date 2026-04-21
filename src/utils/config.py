"""
Config - Loads settings from environment variables / .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Required API keys
    anthropic_api_key: str
    gemini_api_key: str
    elevenlabs_api_key: str

    # Optional tuning
    gemini_model: str = "gemini-2.0-flash"
    claude_model: str = "claude-sonnet-4-20250514"
    elevenlabs_model: str = "eleven_turbo_v2_5"

    # Processing
    max_concurrent_tts: int = 5      # Max parallel TTS requests
    temp_dir: str = "/tmp/fps_commentator"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
