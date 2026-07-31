from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import AuditLog, UIMessage
from database.session import get_session
from modules.ui.renderer import reload_ui, render

logger = get_logger(__name__)


@require_permission(PermissionLevel.BOT_OWNER)
async def editui_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/editui <key> <new content...>  - live-edit any UI surface."""
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /editui <key> <new text>\nExample: /editui welcome Hey {first_name}, glad you're here!"
        )
        return

    key, *rest = context.args
    content = " ".join(rest)

    async with get_session() as session:
        result = await session.execute(select(UIMessage).where(UIMessage.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            row = UIMessage(key=key, content=content, updated_by=update.effective_user.id)
            session.add(row)
        else:
            row.content = content
            row.updated_by = update.effective_user.id
        session.add(AuditLog(actor_id=update.effective_user.id, action="editui", target=key))

    reload_ui()
    await update.effective_message.reply_text(await render("ui.updated", key=key))


@require_permission(PermissionLevel.USER)
async def ui_preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ui <key> - preview how a UI key currently renders."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /ui <key>")
        return
    key = context.args[0]
    text = await render(key)
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.BOT_OWNER)
async def reloadui_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reloadui - force-clear the UI override cache (rarely needed; writes
    already invalidate it, but useful if a second process wrote directly)."""
    reload_ui()
    await update.effective_message.reply_text("UI cache reloaded.")
