from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.market import service
from modules.shop.service import get_item
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def marketlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/marketlist <item_key> <quantity> <price_per_unit>"""
    if len(context.args) < 3:
        await update.effective_message.reply_text("Usage: /marketlist <item_key> <quantity> <price_per_unit>")
        return
    item_key = context.args[0]
    try:
        quantity = int(context.args[1])
        price_per_unit = int(context.args[2])
    except ValueError:
        await update.effective_message.reply_text("quantity and price_per_unit must be whole numbers.")
        return

    tg_user = update.effective_user
    async with get_session() as session:
        seller = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        listing, error = await service.create_listing(session, seller, item_key, quantity, price_per_unit)

    if error == "invalid_item":
        await update.effective_message.reply_text(await render("shop.item_not_found"))
    elif error == "invalid_amount":
        await update.effective_message.reply_text(await render("market.invalid_amount"))
    elif error == "not_owned":
        await update.effective_message.reply_text(await render("market.not_owned"))
    else:
        item = get_item(item_key)
        await update.effective_message.reply_text(
            await render("market.list_success", id=listing.id, quantity=quantity, item=item["name"],
                          price=price_per_unit),
            parse_mode="Markdown",
        )


@require_permission(PermissionLevel.USER)
async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/market - browse active listings."""
    async with get_session() as session:
        listings = await service.active_listings(session)

    if not listings:
        await update.effective_message.reply_text(await render("market.list_empty"))
        return

    title = await render("market.browse_title")
    lines = [title, ""]
    for listing in listings:
        item = get_item(listing.item_key)
        name = item["name"] if item else listing.item_key
        total = listing.quantity * listing.price_per_unit
        lines.append(f"#{listing.id} - {listing.quantity}x {name} @ {listing.price_per_unit}/ea (total {total})")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def marketbuy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/marketbuy <listing_id>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /marketbuy <listing_id>")
        return
    try:
        listing_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("listing_id must be a number.")
        return

    tg_user = update.effective_user
    async with get_session() as session:
        buyer = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        listing, error = await service.buy_listing(session, buyer, listing_id)

    if error == "not_found":
        await update.effective_message.reply_text(await render("market.not_found"))
    elif error == "self_purchase":
        await update.effective_message.reply_text(await render("market.self_purchase"))
    elif error == "insufficient_funds":
        await update.effective_message.reply_text(await render("shop.buy_insufficient_funds"))
    else:
        item = get_item(listing.item_key)
        await update.effective_message.reply_text(
            await render("market.buy_success", quantity=listing.quantity, item=item["name"],
                          cost=listing.quantity * listing.price_per_unit),
            parse_mode="Markdown",
        )


@require_permission(PermissionLevel.USER)
async def marketcancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/marketcancel <listing_id>"""
    if not context.args:
        await update.effective_message.reply_text("Usage: /marketcancel <listing_id>")
        return
    try:
        listing_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("listing_id must be a number.")
        return

    tg_user = update.effective_user
    async with get_session() as session:
        seller = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        listing, error = await service.cancel_listing(session, seller, listing_id)

    if error == "not_found":
        await update.effective_message.reply_text(await render("market.not_found"))
    elif error == "not_owner":
        await update.effective_message.reply_text(await render("market.not_owner"))
    else:
        await update.effective_message.reply_text(await render("market.cancel_success", id=listing.id))
