from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from core.logging import get_logger
from core.permissions import PermissionLevel, require_permission
from database.models import Ticket, TicketMessage, TicketStatus
from database.session import get_session
from modules.ui.renderer import render

logger = get_logger(__name__)


@require_permission(PermissionLevel.USER)
async def ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ticket <subject> - open a new support ticket (DM only)."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /ticket <subject describing your issue>")
        return
    subject = " ".join(context.args)
    user_id = update.effective_user.id

    async with get_session() as session:
        existing = await session.execute(
            select(Ticket).where(Ticket.user_id == user_id, Ticket.status != TicketStatus.CLOSED)
        )
        if existing.scalar_one_or_none():
            await update.effective_message.reply_text("You already have an open ticket. Use /close first.")
            return

        ticket = Ticket(user_id=user_id, subject=subject)
        session.add(ticket)
        await session.flush()
        session.add(TicketMessage(ticket_id=ticket.id, sender_id=user_id, message=subject, is_staff=False))
        ticket_id = ticket.id

    await update.effective_message.reply_text(await render("support.ticket_created", id=ticket_id, subject=subject))


@require_permission(PermissionLevel.SUPPORT_STAFF)
async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/tickets - staff view of all open tickets."""
    async with get_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.status != TicketStatus.CLOSED).order_by(Ticket.created_at)
        )
        open_tickets = list(result.scalars())

    if not open_tickets:
        await update.effective_message.reply_text(await render("support.ticket_list_empty"))
        return

    lines = [f"#{t.id} [{t.priority}] user {t.user_id} — {t.subject}" for t in open_tickets]
    await update.effective_message.reply_text("\n".join(lines))


@require_permission(PermissionLevel.SUPPORT_STAFF)
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reply <ticket_id> <message> - staff reply, forwarded to the ticket owner's DM."""
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /reply <ticket_id> <message>")
        return
    try:
        ticket_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ticket_id must be a number.")
        return
    message = " ".join(context.args[1:])

    async with get_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            await update.effective_message.reply_text("No such ticket.")
            return
        session.add(TicketMessage(ticket_id=ticket_id, sender_id=update.effective_user.id, message=message, is_staff=True))
        owner_id = ticket.user_id

    try:
        await context.bot.send_message(chat_id=owner_id, text=await render("support.ticket_reply", id=ticket_id, message=message))
    except Exception:
        logger.warning("Could not DM ticket owner %s for ticket #%s", owner_id, ticket_id)

    await update.effective_message.reply_text(f"Reply sent for ticket #{ticket_id}.")


@require_permission(PermissionLevel.USER)
async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/close - closes your own open ticket, or /close <id> for staff."""
    async with get_session() as session:
        if context.args:
            try:
                ticket_id = int(context.args[0])
            except ValueError:
                await update.effective_message.reply_text("ticket_id must be a number.")
                return
            ticket = await session.get(Ticket, ticket_id)
        else:
            result = await session.execute(
                select(Ticket).where(Ticket.user_id == update.effective_user.id, Ticket.status != TicketStatus.CLOSED)
            )
            ticket = result.scalar_one_or_none()

        if ticket is None:
            await update.effective_message.reply_text(await render("support.no_open_ticket"))
            return

        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = dt.datetime.now(dt.timezone.utc)
        ticket_id = ticket.id

    await update.effective_message.reply_text(await render("support.ticket_closed", id=ticket_id))
