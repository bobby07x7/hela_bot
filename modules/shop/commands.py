from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.shop import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    title = await render("shop.list_title")
    lines = [title, ""] + service.format_catalog()
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/buy <item_key> [quantity]"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /buy <item_key> [quantity]")
        return
    item_key = context.args[0]
    quantity = 1
    if len(context.args) > 1:
        try:
            quantity = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("Quantity must be a whole number.")
            return

    item = service.get_item(item_key)
    if item is None:
        await update.effective_message.reply_text(await render("shop.item_not_found"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, cost = await service.buy_item(session, user, item_key, quantity)

    if ok:
        await update.effective_message.reply_text(
            await render("shop.buy_success", quantity=quantity, item=item["name"], cost=cost), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(await render("shop.buy_insufficient_funds"))


@require_permission(PermissionLevel.USER)
async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/sell <item_key> [quantity]"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /sell <item_key> [quantity]")
        return
    item_key = context.args[0]
    quantity = 1
    if len(context.args) > 1:
        try:
            quantity = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("Quantity must be a whole number.")
            return

    item = service.get_item(item_key)
    if item is None:
        await update.effective_message.reply_text(await render("shop.item_not_found"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, received = await service.sell_item(session, user, item_key, quantity)

    if ok:
        await update.effective_message.reply_text(
            await render("shop.sell_success", quantity=quantity, item=item["name"], amount=received), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(await render("shop.sell_not_owned"))


@require_permission(PermissionLevel.USER)
async def use_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/use <item_key>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /use <item_key>")
        return
    item_key = context.args[0]
    item = service.get_item(item_key)
    if item is None:
        await update.effective_message.reply_text(await render("shop.item_not_found"))
        return
    if not item.get("usable"):
        await update.effective_message.reply_text(await render("shop.use_not_usable"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, description = await service.use_item(session, user, item_key)

    if ok:
        await update.effective_message.reply_text(
            await render("shop.use_success", item=item["name"], effect=description), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(await render("shop.use_not_owned"))
