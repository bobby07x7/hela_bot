from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.themes import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def settheme_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/settheme <name> - group-admin only."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /settheme <name>\nOptions: " + ", ".join(service.theme_names()))
        return
    theme_name = context.args[0].lower()
    chat = update.effective_chat

    async with get_session() as session:
        ok = await service.set_group_theme(session, chat.id, chat.title, theme_name)

    if ok:
        await update.effective_message.reply_text(await render("themes.set_success", theme=theme_name), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(
            await render("themes.invalid", themes=", ".join(service.theme_names()))
        )


@require_permission(PermissionLevel.USER)
async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/theme - shows the current group's theme."""
    chat = update.effective_chat
    async with get_session() as session:
        current = await service.get_group_theme(session, chat.id)

    await update.effective_message.reply_text(
        await render("themes.current", theme=current, themes=", ".join(service.theme_names())), parse_mode="Markdown"
    )
