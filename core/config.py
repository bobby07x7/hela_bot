"""
Central configuration for Hela Bot.

All runtime configuration is loaded from environment variables (or a `.env`
file in development). Nothing here should ever contain a hard-coded secret.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Telegram ---
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field(default="HelaBot", alias="BOT_USERNAME")

    # --- Access control (comma separated Telegram user IDs) ---
    owner_ids: List[int] = Field(default_factory=list, alias="OWNER_IDS")
    developer_ids: List[int] = Field(default_factory=list, alias="DEVELOPER_IDS")
    support_staff_ids: List[int] = Field(default_factory=list, alias="SUPPORT_STAFF_IDS")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://hela:hela@localhost:5432/hela",
        alias="DATABASE_URL",
    )

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # --- Runtime flags ---
    maintenance_mode: bool = Field(default=False, alias="MAINTENANCE_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_locale: str = Field(default="en", alias="DEFAULT_LOCALE")

    # --- Dashboard / API ---
    api_secret_key: str = Field(default="change-me", alias="API_SECRET_KEY")
    api_port: int = Field(default=8080, alias="API_PORT")

    # --- Economy tuning ---
    daily_reward_min: int = Field(default=100, alias="DAILY_REWARD_MIN")
    daily_reward_max: int = Field(default=500, alias="DAILY_REWARD_MAX")
    work_reward_min: int = Field(default=20, alias="WORK_REWARD_MIN")
    work_reward_max: int = Field(default=150, alias="WORK_REWARD_MAX")
    work_cooldown_seconds: int = Field(default=60 * 30, alias="WORK_COOLDOWN_SECONDS")

    @field_validator("owner_ids", "developer_ids", "support_staff_ids", mode="before")
    @classmethod
    def _split_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        return [int(x.strip()) for x in str(value).split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - import this everywhere instead of
    instantiating Settings() directly, so env is parsed exactly once."""
    return Settings()
