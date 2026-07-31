from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import LotteryEntry, LotteryRound, User

SLOT_SYMBOLS = ["\U0001F352", "\U0001F34B", "\U0001F514", "\U0001F48E", "\U00002B50"]  # cherry lemon bell gem star


def flip_coin(bet: int, choice: str, rng: random.Random | None = None) -> tuple[str, bool, int]:
    """Pure. choice is 'heads' or 'tails'. Returns (result, won, payout)."""
    rng = rng or random
    result = rng.choice(["heads", "tails"])
    won = result == choice
    payout = bet if won else -bet
    return result, won, payout


def roll_dice(bet: int, target: int, rng: random.Random | None = None) -> tuple[int, bool, int]:
    """Pure. Rolls a d6; player wins double their bet if roll >= target
    (target must be 2-6, since needing a 1 would be a guaranteed win)."""
    rng = rng or random
    roll = rng.randint(1, 6)
    won = roll >= target
    payout = bet * 2 if won else -bet
    return roll, won, payout


def spin_slots(bet: int, rng: random.Random | None = None) -> tuple[str, str, str, bool, int]:
    """Pure. Three matching symbols pays 5x, any two matching pays back the
    bet (break-even), no match loses the bet."""
    rng = rng or random
    a, b, c = rng.choice(SLOT_SYMBOLS), rng.choice(SLOT_SYMBOLS), rng.choice(SLOT_SYMBOLS)
    if a == b == c:
        return a, b, c, True, bet * 5
    if a == b or b == c or a == c:
        return a, b, c, True, 0  # push - no gain, no loss
    return a, b, c, False, -bet


async def get_or_open_round(session: AsyncSession) -> LotteryRound:
    result = await session.execute(select(LotteryRound).where(LotteryRound.is_open.is_(True)))
    round_ = result.scalar_one_or_none()
    if round_ is None:
        round_ = LotteryRound(is_open=True, pot=0)
        session.add(round_)
        await session.flush()
    return round_


async def buy_tickets(session: AsyncSession, user: User, telegram_id: int, tickets: int, ticket_price: int) -> tuple[bool, int, int]:
    """Returns (success, cost, new_pot)."""
    if tickets <= 0:
        return False, 0, 0
    cost = tickets * ticket_price
    if user.balance < cost:
        return False, cost, 0

    round_ = await get_or_open_round(session)
    user.balance -= cost
    round_.pot += cost

    result = await session.execute(
        select(LotteryEntry).where(LotteryEntry.round_id == round_.id, LotteryEntry.user_id == telegram_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        entry = LotteryEntry(round_id=round_.id, user_id=telegram_id, tickets=tickets)
        session.add(entry)
    else:
        entry.tickets += tickets
    await session.flush()
    return True, cost, round_.pot


async def lottery_status(session: AsyncSession, telegram_id: int) -> tuple[int, int, int, int]:
    """Returns (round_id, pot, your_tickets, total_tickets)."""
    round_ = await get_or_open_round(session)
    result = await session.execute(select(LotteryEntry).where(LotteryEntry.round_id == round_.id))
    entries = list(result.scalars())
    your_tickets = sum(e.tickets for e in entries if e.user_id == telegram_id)
    total_tickets = sum(e.tickets for e in entries)
    return round_.id, round_.pot, your_tickets, total_tickets


async def draw_lottery(session: AsyncSession, rng: random.Random | None = None) -> tuple[int, int, int | None]:
    """Closes the current round and picks a winner weighted by ticket count.
    Returns (round_id, pot, winner_telegram_id_or_None)."""
    rng = rng or random
    round_ = await get_or_open_round(session)
    result = await session.execute(select(LotteryEntry).where(LotteryEntry.round_id == round_.id))
    entries = list(result.scalars())

    winner_id = None
    if entries:
        weighted_pool = []
        for e in entries:
            weighted_pool.extend([e.user_id] * e.tickets)
        winner_id = rng.choice(weighted_pool)

        if winner_id is not None:
            winner_result = await session.execute(select(User).where(User.telegram_id == winner_id))
            winner = winner_result.scalar_one_or_none()
            if winner is not None:
                winner.balance += round_.pot

    round_.is_open = False
    round_.winner_telegram_id = winner_id
    pot = round_.pot
    round_id = round_.id
    await session.flush()
    return round_id, pot, winner_id
