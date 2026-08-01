from __future__ import annotations

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.wordfilter import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.GROUP_ADMIN)
async def addfilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/addfilter <word>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /addfilter <word>")
        return
    word = " ".join(context.args)
    chat_id = update.effective_chat.id

    async with get_session() as session:
        added = await service.add_word(session, chat_id, word, update.effective_user.id)

    if added:
        await update.effective_message.reply_text(await render("wordfilter.added", word=word), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(await render("wordfilter.already_added"))


@require_permission(PermissionLevel.GROUP_ADMIN)
async def removefilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/removefilter <word>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /removefilter <word>")
        return
    word = " ".join(context.args)
    chat_id = update.effective_chat.id

    async with get_session() as session:
        removed = await service.remove_word(session, chat_id, word)

    if removed:
        await update.effective_message.reply_text(await render("wordfilter.removed", word=word), parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(await render("wordfilter.not_found"))


@require_permission(PermissionLevel.GROUP_ADMIN)
async def filterlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        words = await service.get_filtered_words(session, update.effective_chat.id)

    if not words:
        await update.effective_message.reply_text(await render("wordfilter.list_empty"))
        return

    title = await render("wordfilter.list_title")
    await update.effective_message.reply_text(title + "\n\n" + ", ".join(f"`{w}`" for w in words), parse_mode="Markdown")


async def filter_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs on every text message in groups; deletes it if it contains a
    filtered word. Registered as a low-priority MessageHandler in core/bot.py
    so it doesn't interfere with command parsing."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or chat.type not in ("group", "supergroup"):
        return
    if not message.text:
        return

    async with get_session() as session:
        words = await service.get_filtered_words(session, chat.id)
    if not words:
        return

    matched = service.message_contains_filtered_word(message.text, words)
    if matched is None:
        return

    try:
        await message.delete()
    except TelegramError:
        return

    name = update.effective_user.first_name or update.effective_user.username or "someone"
    try:
        await context.bot.send_message(chat_id=chat.id, text=await render("wordfilter.message_deleted", name=name))
    except TelegramError:
        pass
