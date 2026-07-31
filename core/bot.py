from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, TypeHandler

from core.common_commands import error_handler, help_command, start_command, track_chat
from core.config import get_settings
from core.logging import get_logger
from modules.admin import commands as admin_commands
from modules.economy import commands as economy_commands
from modules.forcejoin import commands as forcejoin_commands
from modules.gambling import commands as gambling_commands
from modules.guild import commands as guild_commands
from modules.moderation import commands as moderation_commands
from modules.owner import commands as owner_commands
from modules.pets import commands as pets_commands
from modules.premium import commands as premium_commands
from modules.rpg import commands as rpg_commands
from modules.shop import commands as shop_commands
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
    application.add_handler(CommandHandler("deposit", economy_commands.deposit_command))
    application.add_handler(CommandHandler("withdraw", economy_commands.withdraw_command))
    application.add_handler(CommandHandler("profile", economy_commands.profile_command))
    application.add_handler(CommandHandler("rank", economy_commands.rank_command))
    application.add_handler(CommandHandler("leaderboard", economy_commands.leaderboard_command))

    # --- RPG ---
    application.add_handler(CommandHandler("adventure", rpg_commands.adventure_command))
    application.add_handler(CommandHandler("hunt", rpg_commands.hunt_command))
    application.add_handler(CommandHandler("fight", rpg_commands.fight_command))
    application.add_handler(CommandHandler("inventory", rpg_commands.inventory_command))

    # --- Shop ---
    application.add_handler(CommandHandler("shop", shop_commands.shop_command))
    application.add_handler(CommandHandler("buy", shop_commands.buy_command))
    application.add_handler(CommandHandler("sell", shop_commands.sell_command))
    application.add_handler(CommandHandler("use", shop_commands.use_command))

    # --- Pets ---
    application.add_handler(CommandHandler("adopt", pets_commands.adopt_command))
    application.add_handler(CommandHandler("pets", pets_commands.pets_command))
    application.add_handler(CommandHandler("feed", pets_commands.feed_command))
    application.add_handler(CommandHandler("releasepet", pets_commands.releasepet_command))

    # --- Guild ---
    application.add_handler(CommandHandler("guildcreate", guild_commands.guildcreate_command))
    application.add_handler(CommandHandler("guildjoin", guild_commands.guildjoin_command))
    application.add_handler(CommandHandler("guildleave", guild_commands.guildleave_command))
    application.add_handler(CommandHandler("guildinfo", guild_commands.guildinfo_command))
    application.add_handler(CommandHandler("guildlist", guild_commands.guildlist_command))
    application.add_handler(CommandHandler("guilddonate", guild_commands.guilddonate_command))
    application.add_handler(CommandHandler("guildkick", guild_commands.guildkick_command))

    # --- Gambling ---
    application.add_handler(CommandHandler("coinflip", gambling_commands.coinflip_command))
    application.add_handler(CommandHandler("dice", gambling_commands.dice_command))
    application.add_handler(CommandHandler("slots", gambling_commands.slots_command))
    application.add_handler(CommandHandler("lotterybuy", gambling_commands.lotterybuy_command))
    application.add_handler(CommandHandler("lottery", gambling_commands.lottery_command))
    application.add_handler(CommandHandler("lotterydraw", gambling_commands.lotterydraw_command))

    # --- Premium ---
    application.add_handler(CommandHandler("premium", premium_commands.premium_command))
    application.add_handler(CommandHandler("grantpremium", premium_commands.grantpremium_command))
    application.add_handler(CommandHandler("revokepremium", premium_commands.revokepremium_command))

    # --- Moderation (group-admin+) ---
    application.add_handler(CommandHandler("warn", moderation_commands.warn_command))
    application.add_handler(CommandHandler("unwarn", moderation_commands.unwarn_command))
    application.add_handler(CommandHandler("warnings", moderation_commands.warnings_command))
    application.add_handler(CommandHandler("mute", moderation_commands.mute_command))
    application.add_handler(CommandHandler("unmute", moderation_commands.unmute_command))
    application.add_handler(CommandHandler("kick", moderation_commands.kick_command))
    application.add_handler(CommandHandler("ban", moderation_commands.ban_command))
    application.add_handler(CommandHandler("unban", moderation_commands.unban_command))
    application.add_handler(CommandHandler("purge", moderation_commands.purge_command))

    # --- Force-join config (group-admin+) ---
    application.add_handler(CommandHandler("addforcejoin", forcejoin_commands.addforcejoin_command))
    application.add_handler(CommandHandler("removeforcejoin", forcejoin_commands.removeforcejoin_command))
    application.add_handler(CommandHandler("forcejoinlist", forcejoin_commands.forcejoinlist_command))

    # --- Bot-admin ---
    application.add_handler(CommandHandler("addcoins", admin_commands.addcoins_command))
    application.add_handler(CommandHandler("removecoins", admin_commands.removecoins_command))
    application.add_handler(CommandHandler("resetuser", admin_commands.resetuser_command))
    application.add_handler(CommandHandler("promote", admin_commands.promote_command))
    application.add_handler(CommandHandler("demote", admin_commands.demote_command))
    application.add_handler(CommandHandler("blacklist", admin_commands.blacklist_command))
    application.add_handler(CommandHandler("unblacklist", admin_commands.unblacklist_command))
    application.add_handler(CommandHandler("groupban", admin_commands.groupban_command))
    application.add_handler(CommandHandler("groupunban", admin_commands.groupunban_command))

    # --- Owner ---
    application.add_handler(CommandHandler("broadcast", owner_commands.broadcast_command))
    application.add_handler(CommandHandler("maintenance", owner_commands.maintenance_command))
    application.add_handler(CommandHandler("stats", owner_commands.stats_command))
    application.add_handler(CommandHandler("shutdown", owner_commands.shutdown_command))

    # --- Support / tickets ---
    application.add_handler(CommandHandler("ticket", support_commands.ticket_command))
    application.add_handler(CommandHandler("tickets", support_commands.tickets_command))
    application.add_handler(CommandHandler("reply", support_commands.reply_command))
    application.add_handler(CommandHandler("close", support_commands.close_command))

    # --- Live UI editor ---
    application.add_handler(CommandHandler("editui", ui_editor.editui_command))
    application.add_handler(CommandHandler("ui", ui_editor.ui_preview_command))
    application.add_handler(CommandHandler("reloadui", ui_editor.reloadui_command))

    application.add_error_handler(error_handler)

    logger.info("Registered %d handler groups", len(application.handlers))
    return application
