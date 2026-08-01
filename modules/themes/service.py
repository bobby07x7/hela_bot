from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GroupChat

THEMES: dict[str, dict[str, str]] = {
    "default": {"border": "\u2728", "accent": "\U0001F31F"},
    "dark": {"border": "\U0001F311", "accent": "\U0001F5A4"},
    "neon": {"border": "\U0001F49C", "accent": "\U0001F4A5"},
    "anime": {"border": "\U0001F338", "accent": "\U0001F338"},
    "minimal": {"border": "-", "accent": "-"},
}
DEFAULT_THEME = "default"


def is_valid_theme(name: str) -> bool:
    return name in THEMES


def theme_names() -> list[str]:
    return list(THEMES.keys())


def apply_theme_header(theme_name: str, title: str) -> str:
    """Pure: wraps a title with the theme's decorative border, e.g.
    apply_theme_header('neon', 'Leaderboard') -> '\U0001F49C Leaderboard \U0001F49C'."""
    theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    border = theme["border"]
    return f"{border} {title} {border}"


async def get_group_theme(session: AsyncSession, chat_id: int) -> str:
    result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat_id))
    group = result.scalar_one_or_none()
    if group is None:
        return DEFAULT_THEME
    return group.settings.get("theme", DEFAULT_THEME)


async def set_group_theme(session: AsyncSession, chat_id: int, title: str | None, theme_name: str) -> bool:
    if not is_valid_theme(theme_name):
        return False
    result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat_id))
    group = result.scalar_one_or_none()
    if group is None:
        group = GroupChat(chat_id=chat_id, title=title)
        session.add(group)
    settings_dict = dict(group.settings or {})
    settings_dict["theme"] = theme_name
    group.settings = settings_dict
    await session.flush()
    return True
