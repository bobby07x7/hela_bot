"""
Central configuration for Hela Bot.

All runtime configuration is loaded from environment variables (or a `.env`
file in development). Nothing here should ever contain a hard-coded secret.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Query params that plain libpq-style URLs use (Neon, Heroku, Railway's
# Postgres plugin, etc.) but that asyncpg's SQLAlchemy dialect does not
# understand. If we pass them straight through, asyncpg raises
# `TypeError: connect() got an unexpected keyword argument 'channel_binding'`
# (or similar) and the whole process crashes on boot - which is exactly
# what silently breaks `/start` with no visible symptom other than "the bot
# never answers".
_UNSUPPORTED_ASYNC_PG_QUERY_PARAMS = {"channel_binding", "options"}


def normalize_database_url(raw_url: str) -> str:
    """Make a copy-pasted Postgres URL (from Neon, Railway, Heroku, Supabase,
    etc.) safe to hand to SQLAlchemy's asyncpg dialect:

    - `postgres://` / `postgresql://` -> `postgresql+asyncpg://`
    - `sslmode=require` -> `ssl=true` (the query param asyncpg's dialect
      actually understands)
    - drops query params asyncpg doesn't accept (`channel_binding`, `options`)

    sqlite:// and already-correct postgresql+asyncpg:// URLs pass through
    with only the query-param cleanup applied (harmless no-op for sqlite).
    """
    parts = urlsplit(raw_url)
    scheme = parts.scheme

    # Only Postgres URLs need rewriting. Leave sqlite (and anything else)
    # completely untouched - urlsplit/urlunsplit is not a safe no-op
    # round-trip for sqlite's triple-slash form (`sqlite:///:memory:` would
    # lose a slash and silently point somewhere else).
    if scheme not in ("postgres", "postgresql", "postgresql+asyncpg"):
        return raw_url

    scheme = "postgresql+asyncpg"

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned_pairs = []
    for key, value in query_pairs:
        key_lower = key.lower()
        if key_lower in _UNSUPPORTED_ASYNC_PG_QUERY_PARAMS:
            continue
        if key_lower == "sslmode":
            # asyncpg's SQLAlchemy dialect wants `ssl=true`, not `sslmode=require`.
            if value.lower() in ("require", "verify-ca", "verify-full"):
                cleaned_pairs.append(("ssl", "true"))
            continue
        cleaned_pairs.append((key, value))

    new_query = urlencode(cleaned_pairs)
    return urlunsplit((scheme, parts.netloc, parts.path, new_query, parts.fragment))


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

    # --- RPG tuning ---
    adventure_cooldown_seconds: int = Field(default=60 * 20, alias="ADVENTURE_COOLDOWN_SECONDS")
    hunt_cooldown_seconds: int = Field(default=60 * 10, alias="HUNT_COOLDOWN_SECONDS")
    fight_cooldown_seconds: int = Field(default=60 * 15, alias="FIGHT_COOLDOWN_SECONDS")

    # --- Gambling tuning ---
    lottery_ticket_price: int = Field(default=50, alias="LOTTERY_TICKET_PRICE")

    @field_validator("owner_ids", "developer_ids", "support_staff_ids", mode="before")
    @classmethod
    def _split_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        return [int(x.strip()) for x in str(value).split(",") if x.strip()]

    @field_validator("database_url", mode="after")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - import this everywhere instead of
    instantiating Settings() directly, so env is parsed exactly once."""
    return Settings()
