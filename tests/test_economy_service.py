from __future__ import annotations

import datetime as dt

import pytest

from modules.economy import service

pytestmark = pytest.mark.asyncio


async def test_get_or_create_user_is_idempotent(session):
    u1 = await service.get_or_create_user(session, telegram_id=1, username="alice")
    u2 = await service.get_or_create_user(session, telegram_id=1, username="alice")
    assert u1.id == u2.id


async def test_daily_claim_then_cooldown(session):
    user = await service.get_or_create_user(session, telegram_id=2, username="bob")

    claimed, amount, _ = await service.claim_daily(session, user, 100, 100)
    assert claimed is True
    assert amount == 100
    assert user.daily_streak == 1

    claimed_again, amount_again, remaining = await service.claim_daily(session, user, 100, 100)
    assert claimed_again is False
    assert amount_again == 0
    assert remaining.total_seconds() > 0


async def test_daily_streak_increments_within_window(session):
    user = await service.get_or_create_user(session, telegram_id=3, username="carl")
    await service.claim_daily(session, user, 50, 50)
    user.last_daily_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=25)

    claimed, amount, _ = await service.claim_daily(session, user, 50, 50)
    assert claimed is True
    assert user.daily_streak == 2
    assert amount == 55  # base 50 + (streak-1)*5


async def test_work_respects_cooldown(session):
    user = await service.get_or_create_user(session, telegram_id=4, username="dana")
    worked, amount, _ = await service.do_work(session, user, 10, 10, cooldown_seconds=1800)
    assert worked is True
    assert amount == 10

    worked_again, _, remaining = await service.do_work(session, user, 10, 10, cooldown_seconds=1800)
    assert worked_again is False
    assert remaining.total_seconds() > 0


async def test_transfer_moves_balance_and_blocks_overdraft(session):
    sender = await service.get_or_create_user(session, telegram_id=5, username="erin")
    recipient = await service.get_or_create_user(session, telegram_id=6, username="frank")
    sender.balance = 100

    ok = await service.transfer(session, sender, recipient, 40)
    assert ok is True
    assert sender.balance == 60
    assert recipient.balance == 40

    blocked = await service.transfer(session, sender, recipient, 1000)
    assert blocked is False
    assert sender.balance == 60


async def test_top_balances_orders_descending(session):
    a = await service.get_or_create_user(session, telegram_id=7, username="gina")
    b = await service.get_or_create_user(session, telegram_id=8, username="hank")
    a.balance = 10
    b.balance = 500

    top = await service.top_balances(session, limit=10)
    assert [u.telegram_id for u in top[:2]] == [8, 7]


async def test_deposit_and_withdraw(session):
    user = await service.get_or_create_user(session, telegram_id=9, username="ivan")
    user.balance = 100

    assert service.deposit(user, 40) is True
    assert user.balance == 60 and user.bank == 40
    assert service.deposit(user, 1000) is False

    assert service.withdraw(user, 10) is True
    assert user.bank == 30 and user.balance == 70
    assert service.withdraw(user, 999) is False


async def test_apply_xp_levels_up(session):
    user = await service.get_or_create_user(session, telegram_id=10, username="jill")
    levels = service.apply_xp(user, 250)
    assert levels == [2]
    assert user.level == 2
    assert user.xp == 150


async def test_rank_of(session):
    a = await service.get_or_create_user(session, telegram_id=11, username="ken")
    b = await service.get_or_create_user(session, telegram_id=12, username="liz")
    a.balance = 1000
    b.balance = 500

    rank_a, total = await service.rank_of(session, a)
    rank_b, _ = await service.rank_of(session, b)
    assert rank_a == 1
    assert rank_b == 2
    assert total == 2
