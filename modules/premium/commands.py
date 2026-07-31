from __future__ import annotations

import datetime as dt

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/premium - check your own Premium status."""
    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        is_active = user.is_premium and (user.premium_until is None or user.premium_until > dt.datetime.now(dt.timezone.utc))
        until = user.premium_until

    if is_active:
        until_str = until.strftime("%Y-%m-%d") if until else "forever"
        await update.effective_message.reply_text(await render("premium.status_active", until=until_str), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(await render("premium.status_inactive"))


@require_permission(PermissionLevel.BOT_ADMIN)
async def grantpremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/grantpremium <days> - reply to target user."""
    replied = update.effective_message.reply_to_message
    if replied is None or not context.args:
        await update.effective_message.reply_text("Reply to a user with /grantpremium <days>")
        return
    try:
        days = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("days must be a whole number.")
        return

    target = replied.from_user
    async with get_session() as session:
        user = await get_or_create_user(session, target.id, target.username, target.first_name)
        user.is_premium = True
        base = user.premium_until if (user.premium_until and user.premium_until > dt.datetime.now(dt.timezone.utc)) else dt.datetime.now(dt.timezone.utc)
        user.premium_until = base + dt.timedelta(days=days)
        if user.permission_level < int(PermissionLevel.PREMIUM):
            user.permission_level = int(PermissionLevel.PREMIUM)

    await update.effective_message.reply_text(
        await render("premium.grant_success", target=target.first_name, days=days), parse_mode="Markdown"
    )


@require_permission(PermissionLevel.BOT_ADMIN)
async def revokepremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/revokepremium - reply to target user."""
    replied = update.effective_message.reply_to_message
    if replied is None:
        await update.effective_message.reply_text("Reply to a user with /revokepremium")
        return

    target = replied.from_user
    async with get_session() as session:
        user = await get_or_create_user(session, target.id, target.username, target.first_name)
        user.is_premium = False
        user.premium_until = None
        if user.permission_level == int(PermissionLevel.PREMIUM):
            user.permission_level = int(PermissionLevel.USER)

    await update.effective_message.reply_text(await render("premium.revoke_success", target=target.first_name))
