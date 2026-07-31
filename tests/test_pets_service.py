from __future__ import annotations

import datetime as dt

import pytest

from modules.pets import service

pytestmark = pytest.mark.asyncio


async def test_adopt_then_duplicate_adopt_fails(session):
    pet = await service.adopt_pet(session, owner_telegram_id=300, species="dog", name="Rex")
    assert pet is not None
    assert pet.species == "dog"

    duplicate = await service.adopt_pet(session, owner_telegram_id=300, species="cat", name="Whiskers")
    assert duplicate is None


async def test_adopt_invalid_species_fails(session):
    pet = await service.adopt_pet(session, owner_telegram_id=301, species="unicorn", name="Sparkle")
    assert pet is None


async def test_feed_restores_hunger_and_happiness(session):
    pet = await service.adopt_pet(session, owner_telegram_id=302, species="wolf", name="Fang")
    pet.hunger = 50
    pet.happiness = 50
    pet.last_fed_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)

    hunger, happiness = await service.feed_pet(session, pet)
    assert hunger > 50
    assert happiness == 60


async def test_release_pet_removes_it(session):
    pet = await service.adopt_pet(session, owner_telegram_id=303, species="dragon", name="Draco")
    await service.release_pet(session, pet)
    found = await service.get_pet(session, 303)
    assert found is None
