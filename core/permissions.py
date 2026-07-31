"""
Authentication / permission-level system.

Eleven levels as specified, ordered lowest -> highest. Every command
declares the minimum level it requires; `require_permission` resolves the
caller's effective level (static config for owner/dev/support, DB-stored
level for premium/vip/moderator, live Telegram API check for group-admin
and group-owner) and rejects anything below the threshold.
"""
from __future__ import annotations

import enum
import functools
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from database.session import get_session
from modules.ui.renderer import render


class PermissionLevel(enum.IntEnum):
    GUEST = 0
    USER = 1
    PREMIUM = 2
    VIP = 3
    MODERATOR = 4
    GROUP_ADMIN = 5
    GROUP_OWNER = 6
    SUPPORT_STAFF = 7
    DEVELOPER = 8
    BOT_ADMIN = 9
    SUPER_ADMIN = 10
    BOT_OWNER = 11


async def resolve_permission_level(update: Update) -> PermissionLevel:
    """Work out the highest permission level the calling user currently holds."""
    settings = get_settings()
    user = update.effective_user
    chat = update.effective_chat
    if user is None:
        return PermissionLevel.GUEST

    # Static, config-driven top tiers.
    if user.id in settings.owner_ids:
        return PermissionLevel.BOT_OWNER
    if user.id in settings.developer_ids:
        return PermissionLevel.DEVELOPER
    if user.id in settings.support_staff_ids:
        return PermissionLevel.SUPPORT_STAFF

    # Live group-admin / group-owner check (only meaningful in groups).
    group_level = PermissionLevel.GUEST
    if chat is not None and chat.type in ("group", "supergroup"):
        try:
            member = await chat.get_member(user.id)
            if member.status == "creator":
                group_level = PermissionLevel.GROUP_OWNER
            elif member.status == "administrator":
                group_level = PermissionLevel.GROUP_ADMIN
        except Exception:
            pass

    # DB-stored level (premium / vip / moderator / bot_admin / super_admin
    # granted via /promote, or plain USER default).
    db_level = PermissionLevel.USER
    async with get_session() as session:
        from database.models import User
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.telegram_id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user is not None:
            if db_user.is_banned:
                return PermissionLevel.GUEST
            db_level = PermissionLevel(int(db_user.permission_level))

    return max(group_level, db_level)


def require_permission(minimum: PermissionLevel) -> Callable:
    """Decorator for command handlers: async def handler(update, context)."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            settings = get_settings()

            if settings.maintenance_mode and update.effective_user.id not in settings.owner_ids:
                await update.effective_message.reply_text(await render("maintenance_mode"))
                return

            level = await resolve_permission_level(update)
            if level < minimum:
                await update.effective_message.reply_text(
                    await render(
                        "permission_denied",
                        required=minimum.name,
                        current=level.name,
                    )
                )
                return
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator
