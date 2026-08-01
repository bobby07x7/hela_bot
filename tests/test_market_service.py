from __future__ import annotations

import pytest

from modules.economy.service import get_or_create_user
from modules.market import service
from modules.shop.service import buy_item

pytestmark = pytest.mark.asyncio


async def test_create_listing_escrows_inventory(session):
    seller = await get_or_create_user(session, telegram_id=600, username="seller")
    seller.balance = 1000
    await buy_item(session, seller, "potion", 5)

    listing, error = await service.create_listing(session, seller, "potion", 3, 30)
    assert error is None
    assert listing.quantity == 3

    row = await service._get_inventory_row(session, seller, "potion")
    assert row.quantity == 2  # 5 bought - 3 escrowed


async def test_create_listing_fails_without_enough_stock(session):
    seller = await get_or_create_user(session, telegram_id=601, username="seller2")
    listing, error = await service.create_listing(session, seller, "potion", 3, 30)
    assert listing is None
    assert error == "not_owned"


async def test_buy_listing_transfers_coins_and_items(session):
    seller = await get_or_create_user(session, telegram_id=602, username="seller3")
    buyer = await get_or_create_user(session, telegram_id=603, username="buyer1")
    seller.balance = 1000
    buyer.balance = 1000
    await buy_item(session, seller, "potion", 5)
    listing, _ = await service.create_listing(session, seller, "potion", 5, 20)

    result, error = await service.buy_listing(session, buyer, listing.id)
    assert error is None
    assert buyer.balance == 900  # 1000 - (5*20)
    assert seller.balance == 850  # 1000 - (5*50 to buy stock) + (5*20 sale proceeds)

    buyer_row = await service._get_inventory_row(session, buyer, "potion")
    assert buyer_row.quantity == 5


async def test_buy_listing_blocks_self_purchase(session):
    seller = await get_or_create_user(session, telegram_id=604, username="seller4")
    seller.balance = 1000
    await buy_item(session, seller, "potion", 2)
    listing, _ = await service.create_listing(session, seller, "potion", 2, 10)

    result, error = await service.buy_listing(session, seller, listing.id)
    assert result is None
    assert error == "self_purchase"


async def test_buy_listing_blocks_insufficient_funds(session):
    seller = await get_or_create_user(session, telegram_id=605, username="seller5")
    buyer = await get_or_create_user(session, telegram_id=606, username="buyer2")
    seller.balance = 1000
    buyer.balance = 5
    await buy_item(session, seller, "sword", 1)
    listing, _ = await service.create_listing(session, seller, "sword", 1, 500)

    result, error = await service.buy_listing(session, buyer, listing.id)
    assert result is None
    assert error == "insufficient_funds"


async def test_cancel_listing_returns_escrowed_items(session):
    seller = await get_or_create_user(session, telegram_id=607, username="seller6")
    seller.balance = 1000
    await buy_item(session, seller, "shield", 1)
    listing, _ = await service.create_listing(session, seller, "shield", 1, 100)

    result, error = await service.cancel_listing(session, seller, listing.id)
    assert error is None
    row = await service._get_inventory_row(session, seller, "shield")
    assert row.quantity == 1


async def test_cancel_listing_blocks_non_owner(session):
    seller = await get_or_create_user(session, telegram_id=608, username="seller7")
    other = await get_or_create_user(session, telegram_id=609, username="rando")
    seller.balance = 1000
    await buy_item(session, seller, "fishing_rod", 1)
    listing, _ = await service.create_listing(session, seller, "fishing_rod", 1, 50)

    result, error = await service.cancel_listing(session, other, listing.id)
    assert result is None
    assert error == "not_owner"
