from __future__ import annotations

import time

from sqlalchemy import func, select
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from core.config import get_settings
from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import AuditLog, BroadcastLog, GroupChat, Ticket, TicketStatus, User
from database.session import get_session
from modules.ui.renderer import render

logger = get_logger(__name__)
_START_TIME = time.monotonic()


@require_permission(PermissionLevel.BOT_OWNER)
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/broadcast <message> - sends to every known user (DM) and group."""
    message = " ".join(context.args) if context.args else None
    if update.effective_message.reply_to_message:
        message = update.effective_message.reply_to_message.text or message
    if not message:
        await update.effective_message.reply_text("Usage: /broadcast <message> (or reply to a message)")
        return

    async with get_session() as session:
        user_ids = [row[0] for row in await session.execute(select(User.telegram_id))]
        group_ids = [row[0] for row in await session.execute(select(GroupChat.chat_id))]

    targets = user_ids + group_ids
    await update.effective_message.reply_text(await render("owner.broadcast_started", total=len(targets)))

    success, failed = 0, 0
    for chat_id in targets:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)
            success += 1
        except Forbidden:
            failed += 1
        except TelegramError:
            failed += 1

    async with get_session() as session:
        session.add(BroadcastLog(sent_by=update.effective_user.id, total=len(targets), success=success, failed=failed))
        session.add(AuditLog(actor_id=update.effective_user.id, action="broadcast",
                              meta={"total": len(targets), "success": success, "failed": failed}))

    await update.effective_message.reply_text(
        await render("owner.broadcast_done", total=len(targets), success=success, failed=failed)
    )


@require_permission(PermissionLevel.BOT_OWNER)
async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/maintenance <on|off> - toggle maintenance mode for this process."""
    settings = get_settings()
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.effective_message.reply_text("Usage: /maintenance <on|off>")
        return

    settings.maintenance_mode = context.args[0].lower() == "on"

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="maintenance",
                              meta={"enabled": settings.maintenance_mode}))

    key = "owner.maintenance_on" if settings.maintenance_mode else "owner.maintenance_off"
    await update.effective_message.reply_text(await render(key), parse_mode=ParseMode.MARKDOWN)


@require_permission(PermissionLevel.DEVELOPER)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        groups = (await session.execute(select(func.count()).select_from(GroupChat))).scalar_one()
        open_tickets = (
            await session.execute(select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.OPEN))
        ).scalar_one()

    uptime_seconds = int(time.monotonic() - _START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    text = await render(
        "owner.stats", users=users, groups=groups, tickets=open_tickets, uptime=f"{hours}h {minutes}m"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
