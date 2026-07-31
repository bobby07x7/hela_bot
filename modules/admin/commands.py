from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import AuditLog, GroupChat
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.ui.renderer import render

logger = get_logger(__name__)

# Levels an admin is allowed to grant via /promote - deliberately excludes
# the config-driven top tiers (DEVELOPER/SUPPORT_STAFF/BOT_OWNER), which
# only come from OWNER_IDS/DEVELOPER_IDS/SUPPORT_STAFF_IDS in .env.
_PROMOTABLE_LEVELS = {
    "user": PermissionLevel.USER,
    "premium": PermissionLevel.PREMIUM,
    "vip": PermissionLevel.VIP,
    "moderator": PermissionLevel.MODERATOR,
    "bot_admin": PermissionLevel.BOT_ADMIN,
    "super_admin": PermissionLevel.SUPER_ADMIN,
}


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


@require_permission(PermissionLevel.SUPER_ADMIN)
async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/promote <level> - reply to target user. level is one of:
    user, premium, vip, moderator, bot_admin, super_admin"""
    target = _resolve_target(update)
    if target is None or not context.args:
        await update.effective_message.reply_text(
            "Reply to a user with /promote <level>\nLevels: " + ", ".join(_PROMOTABLE_LEVELS)
        )
        return

    level_key = context.args[0].lower()
    if level_key not in _PROMOTABLE_LEVELS:
        await update.effective_message.reply_text("Unknown level. Choose one of: " + ", ".join(_PROMOTABLE_LEVELS))
        return
    level = _PROMOTABLE_LEVELS[level_key]

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.permission_level = int(level)
        session.add(AuditLog(actor_id=update.effective_user.id, action="promote", target=str(target.id),
                              meta={"level": level.name}))

    await update.effective_message.reply_text(
        await render("admin.promote_success", target=target.first_name, level=level.name), parse_mode="Markdown"
    )


@require_permission(PermissionLevel.SUPER_ADMIN)
async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/demote - reply to target user, resets them to plain USER."""
    target = _resolve_target(update)
    if target is None:
        await update.effective_message.reply_text("Reply to a user with /demote")
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.permission_level = int(PermissionLevel.USER)
        session.add(AuditLog(actor_id=update.effective_user.id, action="demote", target=str(target.id)))

    await update.effective_message.reply_text(
        await render("admin.demote_success", target=target.first_name, level=PermissionLevel.USER.name),
        parse_mode="Markdown",
    )


@require_permission(PermissionLevel.BOT_ADMIN)
async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/blacklist - reply to target user, globally bans them from the bot."""
    target = _resolve_target(update)
    if target is None:
        await update.effective_message.reply_text("Reply to a user with /blacklist [reason]")
        return
    reason = " ".join(context.args) if context.args else None

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.is_banned = True
        db_user.ban_reason = reason
        session.add(AuditLog(actor_id=update.effective_user.id, action="blacklist", target=str(target.id),
                              meta={"reason": reason}))

    await update.effective_message.reply_text(await render("admin.blacklist_success", target=target.first_name))


@require_permission(PermissionLevel.BOT_ADMIN)
async def unblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unblacklist - reply to target user, lifts a global ban."""
    target = _resolve_target(update)
    if target is None:
        await update.effective_message.reply_text("Reply to a user with /unblacklist")
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        db_user.is_banned = False
        db_user.ban_reason = None
        session.add(AuditLog(actor_id=update.effective_user.id, action="unblacklist", target=str(target.id)))

    await update.effective_message.reply_text(await render("admin.unblacklist_success", target=target.first_name))


@require_permission(PermissionLevel.BOT_ADMIN)
async def groupban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/groupban - bans the current group from using Hela Bot entirely."""
    chat = update.effective_chat
    async with get_session() as session:
        result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat.id))
        group = result.scalar_one_or_none()
        if group is None:
            group = GroupChat(chat_id=chat.id, title=chat.title)
            session.add(group)
        group.is_banned = True
        session.add(AuditLog(actor_id=update.effective_user.id, action="groupban", target=str(chat.id)))

    await update.effective_message.reply_text(await render("admin.groupban_success"))


@require_permission(PermissionLevel.BOT_ADMIN)
async def groupunban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/groupunban - lifts a group ban for the current group."""
    chat = update.effective_chat
    async with get_session() as session:
        result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat.id))
        group = result.scalar_one_or_none()
        if group is not None:
            group.is_banned = False
        session.add(AuditLog(actor_id=update.effective_user.id, action="groupunban", target=str(chat.id)))

    await update.effective_message.reply_text(await render("admin.groupunban_success"))
