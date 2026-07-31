from __future__ import annotations

import functools
from typing import Callable

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.forcejoin import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def addforcejoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addforcejoin <@channel> - group admins only, adds a mandatory-join channel."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /addforcejoin <@channel>")
        return
    channel = context.args[0]

    async with get_session() as session:
        group = await service.get_or_create_group(session, update.effective_chat.id, update.effective_chat.title)
        service.add_channel(group, channel)

    await update.effective_message.reply_text(await render("forcejoin.added", channel=channel))


@require_permission(PermissionLevel.GROUP_ADMIN)
async def removeforcejoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/removeforcejoin <@channel>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /removeforcejoin <@channel>")
        return
    channel = context.args[0]

    async with get_session() as session:
        group = await service.get_or_create_group(session, update.effective_chat.id, update.effective_chat.title)
        removed = service.remove_channel(group, channel)

    if removed:
        await update.effective_message.reply_text(await render("forcejoin.removed", channel=channel))
    else:
        await update.effective_message.reply_text("That channel wasn't in the force-join list.")


@require_permission(PermissionLevel.GROUP_ADMIN)
async def forcejoinlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        group = await service.get_or_create_group(session, update.effective_chat.id, update.effective_chat.title)
        channels = list(group.force_join_channels or [])

    if not channels:
        await update.effective_message.reply_text(await render("forcejoin.list_empty"))
        return

    title = await render("forcejoin.list_title")
    await update.effective_message.reply_text(title + "\n\n" + "\n".join(channels), parse_mode="Markdown")


def require_joined(func: Callable) -> Callable:
    """Decorator: stack this UNDER @require_permission on any command that
    should be gated by the current group's force-join channels, e.g.:

        @require_permission(PermissionLevel.USER)
        @require_joined
        async def daily_command(update, context): ...

    Exempt users (User.force_join_exempt, checked via get_or_create_user by
    the wrapped command itself) are the wrapped command's responsibility -
    this decorator only knows about the group's channel list."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if chat is not None and chat.type in ("group", "supergroup"):
            async with get_session() as session:
                group = await service.get_or_create_group(session, chat.id, chat.title)
            missing = await service.get_missing_channels(context.bot, group, update.effective_user.id)
            if missing:
                await update.effective_message.reply_text(
                    await render("force_join_required", channels=", ".join(missing))
                )
                return
        return await func(update, context, *args, **kwargs)

    return wrapper
