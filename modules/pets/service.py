from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Pet

SPECIES = ["dog", "cat", "wolf", "dragon", "phoenix"]
HUNGER_DECAY_PER_MINUTE = 0.5  # hunger points lost per minute since last feeding
FEED_HUNGER_RESTORE = 40
FEED_HAPPINESS_GAIN = 10


def current_hunger(stored_hunger: int, last_fed_at: dt.datetime, now: dt.datetime | None = None) -> int:
    """Pure: computes live hunger by decaying `stored_hunger` based on time
    elapsed since `last_fed_at`, clamped to [0, 100]."""
    now = now or dt.datetime.now(dt.timezone.utc)
    minutes_elapsed = max(0.0, (now - last_fed_at).total_seconds() / 60)
    decayed = stored_hunger - minutes_elapsed * HUNGER_DECAY_PER_MINUTE
    return max(0, min(100, int(decayed)))


def apply_feed(stored_hunger: int, happiness: int, last_fed_at: dt.datetime,
               now: dt.datetime | None = None) -> tuple[int, int]:
    """Pure: returns (new_hunger, new_happiness) after feeding right now."""
    now = now or dt.datetime.now(dt.timezone.utc)
    live_hunger = current_hunger(stored_hunger, last_fed_at, now)
    new_hunger = min(100, live_hunger + FEED_HUNGER_RESTORE)
    new_happiness = min(100, happiness + FEED_HAPPINESS_GAIN)
    return new_hunger, new_happiness


async def get_pet(session: AsyncSession, owner_telegram_id: int) -> Pet | None:
    result = await session.execute(select(Pet).where(Pet.owner_telegram_id == owner_telegram_id))
    return result.scalar_one_or_none()


async def adopt_pet(session: AsyncSession, owner_telegram_id: int, species: str, name: str) -> Pet | None:
    if species not in SPECIES:
        return None
    existing = await get_pet(session, owner_telegram_id)
    if existing is not None:
        return None
    pet = Pet(owner_telegram_id=owner_telegram_id, species=species, name=name)
    session.add(pet)
    await session.flush()
    return pet


def is_already_full(stored_hunger: int, last_fed_at: dt.datetime, now: dt.datetime | None = None,
                     threshold: int = 95) -> bool:
    """Pure: whether the pet is too full to bother feeding right now."""
    return current_hunger(stored_hunger, last_fed_at, now) >= threshold


async def feed_pet(session: AsyncSession, pet: Pet) -> tuple[int, int]:
    """Feeds the pet and returns the resulting (hunger, happiness). Callers
    should check `is_already_full` first if they want to short-circuit with
    a different message instead of feeding."""
    new_hunger, new_happiness = apply_feed(pet.hunger, pet.happiness, pet.last_fed_at)
    pet.hunger = new_hunger
    pet.happiness = new_happiness
    pet.last_fed_at = dt.datetime.now(dt.timezone.utc)
    await session.flush()
    return new_hunger, new_happiness


async def release_pet(session: AsyncSession, pet: Pet) -> None:
    await session.delete(pet)
