from __future__ import annotations

import random

import pytest

from modules.economy.service import get_or_create_user
from modules.gambling import service

pytestmark = pytest.mark.asyncio


def test_flip_coin_payout_matches_bet():
    rng = random.Random(1)
    result, won, payout = service.flip_coin(100, "heads", rng=rng)
    assert result in ("heads", "tails")
    assert payout == (100 if won else -100)


def test_roll_dice_payout_is_double_or_negative_bet():
    rng = random.Random(2)
    roll, won, payout = service.roll_dice(50, target=4, rng=rng)
    assert 1 <= roll <= 6
    assert payout == (100 if won else -50)


async def test_buy_tickets_deducts_balance_and_grows_pot(session):
    user = await get_or_create_user(session, telegram_id=500, username="team_rocket")
    user.balance = 1000

    ok, cost, pot = await service.buy_tickets(session, user, 500, tickets=3, ticket_price=50)
    assert ok is True
    assert cost == 150
    assert pot == 150
    assert user.balance == 850


async def test_buy_tickets_fails_when_broke(session):
    user = await get_or_create_user(session, telegram_id=501, username="jessie")
    user.balance = 10

    ok, cost, pot = await service.buy_tickets(session, user, 501, tickets=1, ticket_price=50)
    assert ok is False


async def test_lottery_status_tracks_tickets_across_users(session):
    a = await get_or_create_user(session, telegram_id=502, username="james")
    b = await get_or_create_user(session, telegram_id=503, username="meowth")
    a.balance = 1000
    b.balance = 1000

    await service.buy_tickets(session, a, 502, tickets=2, ticket_price=50)
    await service.buy_tickets(session, b, 503, tickets=3, ticket_price=50)

    round_id, pot, your_tickets, total_tickets = await service.lottery_status(session, 502)
    assert your_tickets == 2
    assert total_tickets == 5
    assert pot == 250


async def test_draw_lottery_pays_winner_and_closes_round(session):
    a = await get_or_create_user(session, telegram_id=504, username="ash")
    a.balance = 1000
    await service.buy_tickets(session, a, 504, tickets=5, ticket_price=50)

    round_id, pot, winner_id = await service.draw_lottery(session, rng=random.Random(1))
    assert winner_id == 504  # only entrant, guaranteed win
    assert pot == 250

    winner = await get_or_create_user(session, telegram_id=504, username="ash")
    assert winner.balance == 1000 - 250 + 250  # spent then won it back


async def test_draw_lottery_with_no_entries_returns_none(session):
    round_id, pot, winner_id = await service.draw_lottery(session, rng=random.Random(1))
    assert winner_id is None
    assert pot == 0
