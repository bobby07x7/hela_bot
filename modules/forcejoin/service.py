from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.error import TelegramError

from database.models import GroupChat


async def get_or_create_group(session: AsyncSession, chat_id: int, title: str | None = None) -> GroupChat:
    result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat_id))
    group = result.scalar_one_or_none()
    if group is None:
        group = GroupChat(chat_id=chat_id, title=title)
        session.add(group)
        await session.flush()
    return group


def add_channel(group: GroupChat, channel: str) -> bool:
    """Pure-ish (mutates the passed ORM object's JSON column in place).
    Returns False if the channel was already present."""
    channels = list(group.force_join_channels or [])
    normalized = channel if channel.startswith("@") else f"@{channel}"
    if normalized in channels:
        return False
    channels.append(normalized)
    group.force_join_channels = channels
    group.force_join_enabled = True
    return True


def remove_channel(group: GroupChat, channel: str) -> bool:
    channels = list(group.force_join_channels or [])
    normalized = channel if channel.startswith("@") else f"@{channel}"
    if normalized not in channels:
        return False
    channels.remove(normalized)
    group.force_join_channels = channels
    if not channels:
        group.force_join_enabled = False
    return True


async def get_missing_channels(bot: Bot, group: GroupChat, user_id: int) -> list[str]:
    """Returns the subset of the group's force-join channels the user has
    NOT joined. Best-effort: if the bot can't check a channel (not an admin
    there, wrong username, etc.) that channel is skipped rather than
    blocking everyone."""
    if not group.force_join_enabled or not group.force_join_channels:
        return []

    missing = []
    for channel in group.force_join_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(channel)
        except TelegramError:
            continue
    return missing
