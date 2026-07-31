from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.config import get_settings
from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.session import get_session
from modules.economy.service import get_or_create_user
from modules.gambling import service
from modules.ui.renderer import render

logger = get_logger(__name__)


def _parse_bet(args: list[str]) -> int | None:
    if not args:
        return None
    try:
        bet = int(args[0])
    except ValueError:
        return None
    return bet if bet > 0 else None


@require_permission(PermissionLevel.USER)
async def coinflip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/coinflip <bet> <heads|tails>"""
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /coinflip <bet> <heads|tails>")
        return
    bet = _parse_bet(context.args)
    choice = context.args[1].lower()
    if bet is None or choice not in ("heads", "tails"):
        await update.effective_message.reply_text(await render("gambling.invalid_bet"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        if user.balance < bet:
            await update.effective_message.reply_text(await render("gambling.insufficient_funds"))
            return
        result, won, payout = service.flip_coin(bet, choice)
        user.balance += payout

    key = "gambling.coinflip_win" if won else "gambling.coinflip_lose"
    await update.effective_message.reply_text(await render(key, result=result, amount=abs(payout)), parse_mode="Markdown")


@require_permission(PermissionLevel.USER)
async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/dice <bet> - win double if you roll 4, 5, or 6."""
    bet = _parse_bet(context.args)
    if bet is None:
        await update.effective_message.reply_text(await render("gambling.invalid_bet"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        if user.balance < bet:
            await update.effective_message.reply_text(await render("gambling.insufficient_funds"))
            return
        roll, won, payout = service.roll_dice(bet, target=4)
        user.balance += payout

    outcome_key = "gambling.dice_win" if won else "gambling.dice_lose"
    outcome = await render(outcome_key, amount=abs(payout))
    await update.effective_message.reply_text(
        await render("gambling.dice_result", roll=roll, target=4, outcome=outcome), parse_mode="Markdown"
    )


@require_permission(PermissionLevel.USER)
async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/slots <bet>"""
    bet = _parse_bet(context.args)
    if bet is None:
        await update.effective_message.reply_text(await render("gambling.invalid_bet"))
        return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        if user.balance < bet:
            await update.effective_message.reply_text(await render("gambling.insufficient_funds"))
            return
        a, b, c, won, payout = service.spin_slots(bet)
        user.balance += payout

    if payout > 0:
        outcome = await render("gambling.slots_win", amount=payout)
    elif payout < 0:
        outcome = await render("gambling.slots_lose", amount=abs(payout))
    else:
        outcome = "Push - your bet was returned."
    await update.effective_message.reply_text(
        await render("gambling.slots_result", a=a, b=b, c=c, outcome=outcome), parse_mode="Markdown"
    )


@require_permission(PermissionLevel.USER)
async def lotterybuy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lotterybuy [ticket_count]"""
    settings = get_settings()
    tickets = 1
    if context.args:
        try:
            tickets = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("Ticket count must be a whole number.")
            return

    tg_user = update.effective_user
    async with get_session() as session:
        user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
        ok, cost, pot = await service.buy_tickets(session, user, tg_user.id, tickets, settings.lottery_ticket_price)

    if ok:
        await update.effective_message.reply_text(
            await render("gambling.lottery_buy_success", tickets=tickets, cost=cost, pot=pot), parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(await render("gambling.insufficient_funds"))


@require_permission(PermissionLevel.USER)
async def lottery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lottery - shows the current round's pot and your tickets."""
    tg_user = update.effective_user
    async with get_session() as session:
        round_id, pot, your_tickets, total_tickets = await service.lottery_status(session, tg_user.id)

    await update.effective_message.reply_text(
        await render("gambling.lottery_status", round_id=round_id, pot=pot, your_tickets=your_tickets,
                      total_tickets=total_tickets),
        parse_mode="Markdown",
    )


@require_permission(PermissionLevel.BOT_OWNER)
async def lotterydraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/lotterydraw - owner-only, closes the current round and picks a winner."""
    async with get_session() as session:
        round_id, pot, winner_id = await service.draw_lottery(session)

    if winner_id is None:
        await update.effective_message.reply_text(await render("gambling.lottery_draw_no_entries"))
        return

    await update.effective_message.reply_text(
        await render("gambling.lottery_draw_winner", round_id=round_id, winner=f"`{winner_id}`", pot=pot),
        parse_mode="Markdown",
    )
