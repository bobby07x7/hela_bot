from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import Guild
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.guild import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def guildcreate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text("Usage: /guildcreate <name>")
        return
    name = " ".join(context.args)
    tg_user = update.effective_user

    async with get_session() as session:
        guild, error = await service.create_guild(session, tg_user.id, name)

    if error == "already_in_guild":
        await update.effective_message.reply_text(await render("guild.create_already_in_guild"))
    elif error == "name_taken":
        await update.effective_message.reply_text(await render("guild.create_name_taken"))
    else:
        await update.effective_message.reply_text(await render("guild.create_success", name=guild.name))


@require_permission(PermissionLevel.USER)
async def guildjoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text("Usage: /guildjoin <name>")
        return
    name = " ".join(context.args)
    tg_user = update.effective_user

    async with get_session() as session:
        guild, error = await service.join_guild(session, tg_user.id, name)

    if error == "already_in_guild":
        await update.effective_message.reply_text(await render("guild.create_already_in_guild"))
    elif error == "not_found":
        await update.effective_message.reply_text(await render("guild.join_not_found"))
    else:
        await update.effective_message.reply_text(await render("guild.join_success", name=guild.name))


@require_permission(PermissionLevel.USER)
async def guildleave_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        guild, error = await service.leave_guild(session, tg_user.id)

    if error == "not_in_guild":
        await update.effective_message.reply_text(await render("guild.leave_not_in_guild"))
    elif error == "is_owner":
        await update.effective_message.reply_text(await render("guild.leave_owner_blocked"))
    else:
        await update.effective_message.reply_text(await render("guild.leave_success", name=guild.name))


@require_permission(PermissionLevel.USER)
async def guildinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        if context.args:
            guild = await service.get_guild_by_name(session, " ".join(context.args))
        else:
            membership = await service.get_membership(session, tg_user.id)
            guild = await session.get(Guild, membership.guild_id) if membership else None

        if guild is None:
            await update.effective_message.reply_text(await render("guild.join_not_found"))
            return
        count = await service.member_count(session, guild.id)
        text = await render("guild.info", name=guild.name, level=guild.level, bank=guild.bank, member_count=count)

    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def guildlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        guilds = await service.list_guilds(session)

    if not guilds:
        await update.effective_message.reply_text(await render("guild.list_empty"))
        return

    title = await render("guild.list_title", count=len(guilds))
    lines = [title, ""]
    for g in guilds:
        lines.append(f"- {g.name} (Lv.{g.level}, bank: {g.bank})")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def guilddonate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text("Usage: /guilddonate <amount>")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Amount must be a whole number.")
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        guild, error = await service.donate(session, user, tg_user.id, amount)

    if error == "insufficient_funds":
        await update.effective_message.reply_text(await render("guild.donate_insufficient_funds"))
    elif error == "not_in_guild":
        await update.effective_message.reply_text(await render("guild.leave_not_in_guild"))
    else:
        await update.effective_message.reply_text(
            await render("guild.donate_success", amount=amount, name=guild.name, bank=guild.bank)
        )


@require_permission(PermissionLevel.USER)
async def guildkick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/guildkick - reply to the member you want to remove (guild owner only)."""
    replied = update.effective_message.reply_to_message
    if replied is None:
        await update.effective_message.reply_text("Reply to the guild member you want to kick.")
        return

    tg_user = update.effective_user
    target = replied.from_user
    async with get_session() as session:
        ok, error = await service.kick_member(session, tg_user.id, target.id)
        guild_name = None
        if ok:
            membership = await service.get_membership(session, tg_user.id)
            # membership was for the owner and still exists; re-fetch guild name for the message
            guild = await session.get(Guild, membership.guild_id) if membership else None
            guild_name = guild.name if guild else ""

    if error == "not_permitted":
        await update.effective_message.reply_text(await render("guild.kick_not_permitted"))
    elif error == "target_not_member":
        await update.effective_message.reply_text(await render("guild.kick_target_not_member"))
    else:
        await update.effective_message.reply_html(
            await render("guild.kick_success", target=target.mention_html(), name=guild_name)
        )
