from __future__ import annotations

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import InventoryItem
from database.session import get_session
from modules.economy.service import get_or_create_user, format_timedelta
from modules.rpg import service
from modules.ui.renderer import render

logger = get_logger(__name__)


async def _announce_level_ups(update: Update, name: str, levels_gained: list[int], max_hp: int) -> None:
    for level in levels_gained:
        await update.effective_message.reply_text(
            await render("rpg.level_up", name=name, level=level, max_hp=max_hp), parse_mode="Markdown"
        )


@require_permission(PermissionLevel.USER)
async def adventure_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, amount, xp, story, remaining, levels_gained = await service.do_adventure(
            session, user, settings.adventure_cooldown_seconds
        )
        name = tg_user.first_name or tg_user.username or "Adventurer"
        max_hp = user.max_hp

    if ok:
        await update.effective_message.reply_text(
            await render("rpg.adventure_success", amount=amount, xp=xp, story=story), parse_mode="Markdown"
        )
        await _announce_level_ups(update, name, levels_gained, max_hp)
    else:
        await update.effective_message.reply_text(
            await render("rpg.adventure_cooldown", remaining=format_timedelta(remaining)), parse_mode="Markdown"
        )


@require_permission(PermissionLevel.USER)
async def hunt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    settings = get_settings()
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, creature, amount, xp, remaining, levels_gained = await service.do_hunt(
            session, user, settings.hunt_cooldown_seconds
        )
        name = tg_user.first_name or tg_user.username or "Hunter"
        max_hp = user.max_hp

    if ok:
        await update.effective_message.reply_text(
            await render("rpg.hunt_success", creature=creature, amount=amount, xp=xp), parse_mode="Markdown"
        )
        await _announce_level_ups(update, name, levels_gained, max_hp)
    else:
        await update.effective_message.reply_text(
            await render("rpg.hunt_cooldown", remaining=format_timedelta(remaining)), parse_mode="Markdown"
        )


@require_permission(PermissionLevel.USER)
async def fight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/fight - reply to the user you want to challenge."""
    attacker_tg = update.effective_user
    replied = update.effective_message.reply_to_message
    settings = get_settings()

    if replied is None:
        await update.effective_message.reply_text(await render("rpg.fight_target_required"))
        return
    defender_tg = replied.from_user
    if defender_tg.id == attacker_tg.id:
        await update.effective_message.reply_text(await render("rpg.fight_self"))
        return

    async with get_session() as session:
        attacker = await get_or_create_user(session, attacker_tg.id, attacker_tg.username, attacker_tg.first_name)
        defender = await get_or_create_user(session, defender_tg.id, defender_tg.username, defender_tg.first_name)
        ok, attacker_won, amount, remaining = await service.do_fight(
            session, attacker, defender, settings.fight_cooldown_seconds
        )

    if not ok:
        await update.effective_message.reply_text(
            await render("rpg.fight_cooldown", remaining=format_timedelta(remaining)), parse_mode="Markdown"
        )
        return

    if attacker_won:
        text = await render("rpg.fight_win", target=defender_tg.mention_html(), amount=amount)
    else:
        text = await render("rpg.fight_lose", target=defender_tg.mention_html(), amount=amount)
    await update.effective_message.reply_html(text)


@require_permission(PermissionLevel.USER)
async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        result = await session.execute(select(InventoryItem).where(InventoryItem.user_id == user.id))
        items = list(result.scalars())
        name = tg_user.first_name or tg_user.username or "there"

    if not items:
        await update.effective_message.reply_text(await render("rpg.inventory_empty"))
        return

    title = await render("rpg.inventory_title", name=name)
    lines = [title, ""]
    for item in items:
        lines.append(f"- {item.item_key} x{item.quantity}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
