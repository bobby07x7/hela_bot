from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.economy import service
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with get_session() as session:
        user = await service.get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        text = await render(
            "economy.balance",
            name=tg_user.first_name or tg_user.username or "there",
            balance=user.balance,
            bank=user.bank,
        )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    settings = get_settings()
    async with get_session() as session:
        user = await service.get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        claimed, amount, remaining = await service.claim_daily(
            session, user, settings.daily_reward_min, settings.daily_reward_max
        )
        streak = user.daily_streak

    if claimed:
        text = await render("economy.daily_claimed", amount=amount, streak=streak)
    else:
        text = await render("economy.daily_cooldown", remaining=service.format_timedelta(remaining))
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    settings = get_settings()
    async with get_session() as session:
        user = await service.get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        worked, amount, remaining = await service.do_work(
            session, user, settings.work_reward_min, settings.work_reward_max, settings.work_cooldown_seconds
        )

    if worked:
        text = await render("economy.work_success", amount=amount)
    else:
        text = await render("economy.work_cooldown", remaining=service.format_timedelta(remaining))
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pay <amount> - reply to the person you want to pay."""
    sender_tg = update.effective_user
    replied = update.effective_message.reply_to_message

    if not replied or not context.args:
        await update.effective_message.reply_text("Usage: reply to a user's message with /pay <amount>")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Amount must be a whole number.")
        return

    recipient_tg = replied.from_user
    if recipient_tg.id == sender_tg.id:
        await update.effective_message.reply_text("You can't pay yourself.")
        return

    async with get_session() as session:
        sender = await service.get_or_create_user(session, sender_tg.id, sender_tg.username, sender_tg.first_name)
        recipient = await service.get_or_create_user(session, recipient_tg.id, recipient_tg.username, recipient_tg.first_name)
        ok = await service.transfer(session, sender, recipient, amount)

    if ok:
        text = await render("economy.pay_success", amount=amount, target=recipient_tg.mention_html())
        await update.effective_message.reply_html(text)
    else:
        await update.effective_message.reply_text(await render("economy.pay_insufficient_funds"))


@require_permission(PermissionLevel.USER)
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with get_session() as session:
        top = await service.top_balances(session, limit=10)

    title = await render("economy.leaderboard_title", count=len(top))
    lines = [title, ""]
    for i, u in enumerate(top, start=1):
        name = u.username or u.first_name or f"User {u.telegram_id}"
        lines.append(f"{i}. {name} — {u.balance} coins")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
