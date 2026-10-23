from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore"
    )

    # Telegram
    bot_token: SecretStr
    telegram_api_id: int | None = None
    telegram_api_hash: SecretStr | None = None
    # Local Bot API server (docker: http://telegram-bot-api:8081); None → api.telegram.org
    bot_api_url: str | None = None

    # Storage
    database_url: str = "postgresql+asyncpg://bot:bot@localhost:5433/bot"
    redis_url: str = "redis://localhost:6379/0"

    # Downloader
    max_file_size_mb: int = Field(default=2000, gt=0)
    download_dir: Path = Path("downloads")
    download_timeout_sec: int = Field(default=600, gt=0)
    proxy_url: str | None = None
    ytdlp_cookies_file: Path | None = None

    # Bot behaviour
    rate_limit_per_minute: int = Field(default=5, gt=0)
    cache_ttl_days: int = Field(default=30, gt=0)

    log_level: str = "INFO"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_local_bot_api(self) -> bool:
        return bool(self.bot_api_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from env
