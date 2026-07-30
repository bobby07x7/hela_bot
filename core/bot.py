from __future__ import annotations

from telegram.ext import Application, CommandHandler, TypeHandler
from telegram import Update

from core.common_commands import error_handler, help_command, start_command, track_chat
from core.config import get_settings
from core.logging import get_logger
from modules.admin import commands as admin_commands
from modules.economy import commands as economy_commands
from modules.moderation import commands as moderation_commands
from modules.owner import commands as owner_commands
from modules.support import commands as support_commands
from modules.ui import editor as ui_editor

logger = get_logger(__name__)


def build_application() -> Application:
    settings = get_settings()
    application = Application.builder().token(settings.bot_token).build()

    # Runs first on every single update to keep users/groups tables fresh.
    application.add_handler(TypeHandler(Update, track_chat), group=-1)

    # --- Core ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # --- Economy ---
    application.add_handler(CommandHandler("balance", economy_commands.balance_command))
    application.add_handler(CommandHandler("daily", economy_commands.daily_command))
    application.add_handler(CommandHandler("work", economy_commands.work_command))
    application.add_handler(CommandHandler("pay", economy_commands.pay_command))
    application.add_handler(CommandHandler("leaderboard", economy_commands.leaderboard_command))

    # --- Moderation (group-admin+) ---
    application.add_handler(CommandHandler("warn", moderation_commands.warn_command))
    application.add_handler(CommandHandler("mute", moderation_commands.mute_command))
    application.add_handler(CommandHandler("kick", moderation_commands.kick_command))
    application.add_handler(CommandHandler("ban", moderation_commands.ban_command))

    # --- Bot-admin (economy admin tools) ---
    application.add_handler(CommandHandler("addcoins", admin_commands.addcoins_command))
    application.add_handler(CommandHandler("removecoins", admin_commands.removecoins_command))
    application.add_handler(CommandHandler("resetuser", admin_commands.resetuser_command))

    # --- Owner ---
    application.add_handler(CommandHandler("broadcast", owner_commands.broadcast_command))
    application.add_handler(CommandHandler("maintenance", owner_commands.maintenance_command))
    application.add_handler(CommandHandler("stats", owner_commands.stats_command))

    # --- Support / tickets ---
    application.add_handler(CommandHandler("ticket", support_commands.ticket_command))
    application.add_handler(CommandHandler("tickets", support_commands.tickets_command))
    application.add_handler(CommandHandler("reply", support_commands.reply_command))
    application.add_handler(CommandHandler("close", support_commands.close_command))

    # --- Live UI editor ---
    application.add_handler(CommandHandler("editui", ui_editor.editui_command))
    application.add_handler(CommandHandler("ui", ui_editor.ui_preview_command))

    application.add_error_handler(error_handler)

    logger.info("Registered %d handler groups", len(application.handlers))
    return application
