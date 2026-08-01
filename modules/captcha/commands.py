from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from telegram import ChatPermissions, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import GroupChat
from database.session import get_session
from modules.captcha import service
from modules.ui.renderer import render

logger = get_logger(__name__)

DEFAULT_CAPTCHA_TIMEOUT_SECONDS = 5 * 60


async def _captcha_enabled(session, chat_id: int) -> bool:
    result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat_id))
    group = result.scalar_one_or_none()
    return bool(group and group.settings.get("captcha_enabled"))


async def _kick_if_still_pending(bot, chat_id: int, user_id: int, name: str) -> None:
    pending = await service.get_pending(chat_id, user_id)
    if pending is None:
        return  # already verified or already cleared
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
    except TelegramError:
        logger.warning("Could not auto-kick unverified user %s from chat %s", user_id, chat_id)
    await service.clear_pending(chat_id, user_id)
    try:
        await bot.send_message(chat_id=chat_id, text=await render("captcha.expired_kick", name=name))
    except TelegramError:
        pass


async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered on ChatMemberHandler for new joins. Mutes the new member and
    issues a math captcha if this group has captcha enabled."""
    chat = update.effective_chat
    async with get_session() as session:
        if not await _captcha_enabled(session, chat.id):
            return

    for member in update.message.new_chat_members if update.message else []:
        if member.is_bot:
            continue
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id, user_id=member.id, permissions=ChatPermissions(can_send_messages=False)
            )
        except TelegramError:
            logger.warning("Could not restrict new member %s in chat %s (bot may lack admin rights)", member.id, chat.id)
            continue

        question, answer = service.generate_challenge()
        name = member.first_name or member.username or "there"
        timeout = DEFAULT_CAPTCHA_TIMEOUT_SECONDS
        await service.set_pending(chat.id, member.id, answer, name, ttl_seconds=timeout)

        await update.effective_message.reply_text(
            await render("captcha.challenge", name=name, question=question, minutes=timeout // 60)
        )

        scheduler = context.application.bot_data.get("scheduler")
        if scheduler is not None:
            run_date = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=timeout + 5)
            scheduler.add_job(
                _kick_if_still_pending, "date", run_date=run_date,
                args=[context.bot, chat.id, member.id, name],
                id=f"captcha_kick_{chat.id}_{member.id}", replace_existing=True,
            )


@require_permission(PermissionLevel.USER)
async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/verify <answer>"""
    chat = update.effective_chat
    user = update.effective_user
    if not context.args:
        await update.effective_message.reply_text("Usage: /verify <answer>")
        return

    pending = await service.get_pending(chat.id, user.id)
    if pending is None:
        await update.effective_message.reply_text(await render("captcha.no_pending"))
        return

    if service.check_answer(pending, context.args[0]):
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id, user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True,
                    can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True,
                    can_send_other_messages=True, can_add_web_page_previews=True,
                ),
            )
        except TelegramError:
            pass
        await service.clear_pending(chat.id, user.id)

        scheduler = context.application.bot_data.get("scheduler")
        if scheduler is not None:
            job_id = f"captcha_kick_{chat.id}_{user.id}"
            job = scheduler.get_job(job_id)
            if job is not None:
                job.remove()

        await update.effective_message.reply_text(
            await render("captcha.correct", name=user.first_name or user.username or "there")
        )
    else:
        await update.effective_message.reply_text(await render("captcha.incorrect"))


@require_permission(PermissionLevel.GROUP_ADMIN)
async def togglecaptcha_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/togglecaptcha <on|off>"""
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.effective_message.reply_text("Usage: /togglecaptcha <on|off>")
        return
    enabled = context.args[0].lower() == "on"
    chat = update.effective_chat

    async with get_session() as session:
        result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat.id))
        group = result.scalar_one_or_none()
        if group is None:
            group = GroupChat(chat_id=chat.id, title=chat.title)
            session.add(group)
        settings_dict = dict(group.settings or {})
        settings_dict["captcha_enabled"] = enabled
        group.settings = settings_dict

    key = "captcha.enabled" if enabled else "captcha.disabled"
    await update.effective_message.reply_text(await render(key))
