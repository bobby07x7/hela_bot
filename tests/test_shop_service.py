from __future__ import annotations

import pytest

from modules.economy.service import get_or_create_user
from modules.shop import service

pytestmark = pytest.mark.asyncio


async def test_buy_item_deducts_balance_and_adds_inventory(session):
    user = await get_or_create_user(session, telegram_id=200, username="misty")
    user.balance = 1000

    ok, cost = await service.buy_item(session, user, "potion", 2)
    assert ok is True
    assert cost == 100  # 50 each
    assert user.balance == 900

    row = await service._get_inventory_row(session, user, "potion")
    assert row.quantity == 2


async def test_buy_item_fails_when_broke(session):
    user = await get_or_create_user(session, telegram_id=201, username="brock")
    user.balance = 10

    ok, cost = await service.buy_item(session, user, "sword", 1)
    assert ok is False
    assert cost == 200


async def test_sell_item_requires_ownership(session):
    user = await get_or_create_user(session, telegram_id=202, username="oak")
    ok, received = await service.sell_item(session, user, "sword", 1)
    assert ok is False
    assert received == 0


async def test_buy_then_sell_roundtrip(session):
    user = await get_or_create_user(session, telegram_id=203, username="gary")
    user.balance = 1000
    await service.buy_item(session, user, "shield", 1)
    assert user.balance == 850  # 1000 - 150

    ok, received = await service.sell_item(session, user, "shield", 1)
    assert ok is True
    assert received == 75  # sell_price
    assert user.balance == 925


async def test_use_potion_heals_up_to_max_hp(session):
    user = await get_or_create_user(session, telegram_id=204, username="jessie")
    user.balance = 1000
    user.hp = 60
    user.max_hp = 100
    await service.buy_item(session, user, "potion", 1)

    ok, description = await service.use_item(session, user, "potion")
    assert ok is True
    assert user.hp == 100  # 60 + 50 heal, capped at max_hp
    assert "HP" in description


async def test_use_item_not_owned_fails(session):
    user = await get_or_create_user(session, telegram_id=205, username="james")
    ok, description = await service.use_item(session, user, "potion")
    assert ok is False


async def test_use_non_usable_item_fails(session):
    user = await get_or_create_user(session, telegram_id=206, username="meowth")
    user.balance = 1000
    await service.buy_item(session, user, "sword", 1)
    ok, _ = await service.use_item(session, user, "sword")
    assert ok is False
