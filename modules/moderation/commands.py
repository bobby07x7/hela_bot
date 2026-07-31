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


def _extract_reason(context: ContextTypes.DEFAULT_TYPE, skip: int = 0) -> str:
    args = context.args[skip:] if context.args else []
    return " ".join(args) if args else "No reason provided."


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
async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unwarn - reply to a user, removes their single most recent warning."""
    target = await _require_group_and_target(update)
    if target is None:
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        result = await session.execute(
            select(Warning).where(Warning.user_id == db_user.id).order_by(Warning.created_at.desc())
        )
        warnings = list(result.scalars())
        if not warnings:
            await update.effective_message.reply_html(await render("moderation.no_warnings", target=target.mention_html()))
            return
        await session.delete(warnings[0])
        remaining = len(warnings) - 1
        session.add(AuditLog(actor_id=update.effective_user.id, action="unwarn", target=str(target.id)))

    await update.effective_message.reply_html(
        await render("moderation.unwarn_success", target=target.mention_html(), count=remaining)
    )


@require_permission(PermissionLevel.GROUP_ADMIN)
async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/warnings - reply to a user to list all their warnings in this chat."""
    target = await _require_group_and_target(update)
    if target is None:
        return

    async with get_session() as session:
        db_user = await get_or_create_user(session, target.id, target.username, target.first_name)
        result = await session.execute(
            select(Warning).where(Warning.user_id == db_user.id).order_by(Warning.created_at.desc())
        )
        warnings = list(result.scalars())

    if not warnings:
        await update.effective_message.reply_html(await render("moderation.warnings_empty", target=target.mention_html()))
        return

    title = await render("moderation.warnings_title", target=target.mention_html(), count=len(warnings))
    lines = [title, ""]
    for i, w in enumerate(warnings, start=1):
        lines.append(f"{i}. {w.reason} ({w.created_at:%Y-%m-%d})")
    await update.effective_message.reply_html("\n".join(lines))


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
async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _require_group_and_target(update)
    if target is None:
        return

    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=target.id,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        ),
    )

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="unmute", target=str(target.id),
                              meta={"chat_id": update.effective_chat.id}))

    text = await render("moderation.unmute_success", target=target.mention_html(), actor=update.effective_user.mention_html())
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


@require_permission(PermissionLevel.GROUP_ADMIN)
async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unban <user_id> - Telegram won't let us resolve a banned user's
    @username via reply (they've been kicked out), so this one takes a raw
    numeric ID."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /unban <numeric_user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("user_id must be numeric.")
        return

    chat_id = update.effective_chat.id
    await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="unban", target=str(user_id),
                              meta={"chat_id": chat_id}))

    text = await render("moderation.unban_success", target=f"`{user_id}`", actor=update.effective_user.mention_html())
    await update.effective_message.reply_html(text)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/purge - reply to the message to start deleting from; deletes every
    message between it and this command (inclusive), Telegram API limits apply."""
    chat = update.effective_chat
    replied = update.effective_message.reply_to_message
    if chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(await render("moderation.group_only"))
        return
    if replied is None:
        await update.effective_message.reply_text("Reply to the message you want to purge from.")
        return

    start_id = replied.message_id
    end_id = update.effective_message.message_id
    deleted = 0
    for message_id in range(start_id, end_id + 1):
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=message_id)
            deleted += 1
        except Exception:
            continue

    async with get_session() as session:
        session.add(AuditLog(actor_id=update.effective_user.id, action="purge", meta={"chat_id": chat.id, "count": deleted}))

    await context.bot.send_message(chat_id=chat.id, text=await render("moderation.purge_success", count=deleted))
