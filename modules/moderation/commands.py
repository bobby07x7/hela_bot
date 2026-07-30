from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import AuditLog, Warning
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.ui.renderer import render

logger = get_logger(__name__)


def _extract_reason(context: ContextTypes.DEFAULT_TYPE) -> str:
    return " ".join(context.args) if context.args else "No reason provided."


async def _require_group_and_target(update: Update):
    chat = update.effective_chat
    replied = update.effective_message.reply_to_message
    if chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(await render("moderation.group_only"))
        return None
    if replied is None:
        await update.effective_message.reply_text(await render("moderation.reply_required"))
        return None
    return replied.from_user


@require_permission(PermissionLevel.GROUP_ADMIN)
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_group_and_target(update)
    if target is None:
        return
    reason = _extract_reason(context)

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        session.add(Warning(user_id=db_user.id, chat_id=update.effective_chat.id, reason=reason,
                             issued_by=update.effective_user.id))
        session.add(AuditLog(actor_id=update.effective_user.id, action="warn", target=str(target.id),
                              meta={"reason": reason, "chat_id": update.effective_chat.id}))
        result = await session.execute(select(Warning).where(Warning.user_id == db_user.id))
        count = len(list(result.scalars()))

    text = await render(
        "moderation.warn_issued",
        target=target.mention_html(),
        actor=update.effective_user.mention_html(),
        reason=reason,
        count=count,
    )
    await update.effective_message.reply_html(text)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_group_and_target(update)
    if target is None:
        return

    duration_minutes = None
    if context.args:
        try:
            duration_minutes = int(context.args[0])
        except ValueError:
            duration_minutes = None

    until_date = None
    if duration_minutes:
        until_date = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=duration_minutes)

    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until_date,
    )

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="mute", target=str(target.id),
                              meta={"chat_id": update.effective_chat.id, "duration_minutes": duration_minutes}))

    text = await render("moderation.mute_success", target=target.mention_html(), actor=update.effective_user.mention_html())
    await update.effective_message.reply_html(text)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_group_and_target(update)
    if target is None:
        return

    chat_id = update.effective_chat.id
    await context.bot.ban_chat_member(chat_id=chat_id, user_id=target.id)
    await context.bot.unban_chat_member(chat_id=chat_id, user_id=target.id, only_if_banned=True)

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="kick", target=str(target.id),
                              meta={"chat_id": chat_id}))

    text = await render("moderation.kick_success", target=target.mention_html(), actor=update.effective_user.mention_html())
    await update.effective_message.reply_html(text)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_group_and_target(update)
    if target is None:
        return
    reason = _extract_reason(context)

    await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target.id)

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="ban", target=str(target.id),
                              meta={"chat_id": update.effective_chat.id, "reason": reason}))

    text = await render(
        "moderation.ban_success", target=target.mention_html(), actor=update.effective_user.mention_html(), reason=reason
    )
    await update.effective_message.reply_html(text)
