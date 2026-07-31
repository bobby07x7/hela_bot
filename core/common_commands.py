from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.logging import get_logger
from database.models import GroupChat
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.ui.renderer import render

logger = get_logger(__name__)

HELP_CATEGORIES = {
    "economy": ["/balance", "/daily", "/work", "/pay <amount> (reply)", "/deposit <amount>", "/withdraw <amount>",
                "/profile", "/rank", "/leaderboard"],
    "rpg": ["/adventure", "/hunt", "/fight (reply)", "/inventory"],
    "shop": ["/shop", "/buy <item> [qty]", "/sell <item> [qty]", "/use <item>"],
    "pets": ["/adopt <species> <name>", "/pets", "/feed", "/releasepet"],
    "guild": ["/guildcreate <name>", "/guildjoin <name>", "/guildleave", "/guildinfo [name]", "/guildlist",
              "/guilddonate <amount>", "/guildkick (reply)"],
    "gambling": ["/coinflip <bet> <heads|tails>", "/dice <bet>", "/slots <bet>", "/lotterybuy [count]", "/lottery"],
    "premium": ["/premium"],
    "admin": ["/warn (reply)", "/unwarn (reply)", "/warnings (reply)", "/mute [minutes] (reply)", "/unmute (reply)",
              "/kick (reply)", "/ban [reason] (reply)", "/unban <user_id>", "/purge (reply)",
              "/addcoins <amount> (reply)", "/removecoins <amount> (reply)", "/resetuser (reply)",
              "/promote <level> (reply)", "/demote (reply)", "/blacklist (reply)", "/unblacklist (reply)",
              "/groupban", "/groupunban", "/grantpremium <days> (reply)", "/revokepremium (reply)",
              "/addforcejoin <@channel>", "/removeforcejoin <@channel>", "/forcejoinlist"],
    "owner": ["/broadcast <message>", "/maintenance <on|off>", "/stats", "/shutdown", "/editui <key> <text>",
              "/ui <key>", "/reloadui", "/lotterydraw"],
    "support": ["/ticket <subject>", "/tickets (staff)", "/reply <id> <message> (staff)", "/close [id]"],
}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    async with get_session() as session:
        await get_or_create_user(session, user.id, user.username, user.first_name)

    text = await render("welcome", first_name=user.first_name or "there")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args and context.args[0].lower() in HELP_CATEGORIES:
        category = context.args[0].lower()
        lines = [f"*{category.title()} Commands*", ""]
        lines.extend(HELP_CATEGORIES[category])
        await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return

    text = await render("help")
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs on every update: keeps the users/group_chats tables populated so
    stats, broadcast, and permission checks always have fresh rows."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None:
        return

    async with get_session() as session:
        if user is not None:
            await get_or_create_user(session, user.id, user.username, user.first_name)

        if chat.type in ("group", "supergroup"):
            result = await session.execute(select(GroupChat).where(GroupChat.chat_id == chat.id))
            group = result.scalar_one_or_none()
            if group is None:
                session.add(GroupChat(chat_id=chat.id, title=chat.title))
            elif group.title != chat.title:
                group.title = chat.title


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception while processing update: %s", update, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(await render("error_generic"))
        except Exception:
            pass
