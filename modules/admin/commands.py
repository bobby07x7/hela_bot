from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import AuditLog
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.ui.renderer import render

logger = get_logger(__name__)


def _resolve_target(update: Update):
    replied = update.effective_message.reply_to_message
    return replied.from_user if replied else None


@require_permission(PermissionLevel.BOT_ADMIN)
async def addcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addcoins <amount> - reply to target user."""
    target = _resolve_target(update)
    if target is None or not context.args:
        await update.effective_message.reply_text("Reply to a user with /addcoins <amount>")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Amount must be a whole number.")
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.balance += amount
        session.add(AuditLog(actor_id=update.effective_user.id, action="addcoins", target=str(target.id),
                              meta={"amount": amount}))
        new_balance = db_user.balance

    await update.effective_message.reply_text(
        await render("admin.coins_added", amount=amount, target=target.first_name, balance=new_balance)
    )


@require_permission(PermissionLevel.BOT_ADMIN)
async def removecoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/removecoins <amount> - reply to target user."""
    target = _resolve_target(update)
    if target is None or not context.args:
        await update.effective_message.reply_text("Reply to a user with /removecoins <amount>")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Amount must be a whole number.")
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.balance = max(0, db_user.balance - amount)
        session.add(AuditLog(actor_id=update.effective_user.id, action="removecoins", target=str(target.id),
                              meta={"amount": amount}))
        new_balance = db_user.balance

    await update.effective_message.reply_text(
        await render("admin.coins_removed", amount=amount, target=target.first_name, balance=new_balance)
    )


@require_permission(PermissionLevel.BOT_ADMIN)
async def resetuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/resetuser - reply to target user, wipes their economy progress."""
    target = _resolve_target(update)
    if target is None:
        await update.effective_message.reply_text("Reply to a user with /resetuser")
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.balance = 0
        db_user.bank = 0
        db_user.xp = 0
        db_user.level = 1
        db_user.daily_streak = 0
        db_user.last_daily_at = None
        db_user.last_work_at = None
        session.add(AuditLog(actor_id=update.effective_user.id, action="resetuser", target=str(target.id)))

    await update.effective_message.reply_text(await render("admin.user_reset", target=target.first_name))
