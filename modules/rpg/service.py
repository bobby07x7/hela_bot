from __future__ import annotations

import datetime as dt
import random

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from modules.economy.service import apply_xp

ADVENTURE_STORIES = [
    "You crossed a haunted bridge and found a hidden stash.",
    "You helped a traveling merchant and were rewarded generously.",
    "You explored an old ruin and looted a forgotten chest.",
    "You solved a riddle guarding a mountain shrine.",
    "You navigated a storm at sea and salvaged some cargo.",
]

HUNT_CREATURES = [
    ("Wild Boar", 1.0),
    ("Giant Rat", 0.8),
    ("Forest Wolf", 1.3),
    ("Cave Troll", 1.8),
    ("Shadow Wisp", 1.5),
]

FIGHT_LOOT_PERCENT = 0.15
FIGHT_LOOT_CAP = 500


def _cooldown_check(last_at: dt.datetime | None, cooldown_seconds: int) -> dt.timedelta | None:
    """Returns remaining time if still on cooldown, else None."""
    if last_at is None:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    elapsed = now - last_at
    remaining = dt.timedelta(seconds=cooldown_seconds) - elapsed
    return remaining if remaining.total_seconds() > 0 else None


def roll_adventure(reward_min: int = 50, reward_max: int = 300, rng: random.Random | None = None) -> tuple[int, int, str]:
    """Pure: returns (coins, xp, story_text). No DB/cooldown logic here so
    it's trivially unit-testable."""
    rng = rng or random
    amount = rng.randint(reward_min, reward_max)
    xp = max(5, amount // 10)
    story = rng.choice(ADVENTURE_STORIES)
    return amount, xp, story


def roll_hunt(reward_min: int = 20, reward_max: int = 120, rng: random.Random | None = None) -> tuple[str, int, int]:
    """Pure: returns (creature_name, coins, xp). Rarer/tougher creatures
    give a multiplier on the base roll."""
    rng = rng or random
    creature, multiplier = rng.choices(
        HUNT_CREATURES, weights=[1 / m for _, m in HUNT_CREATURES], k=1
    )[0]
    base = rng.randint(reward_min, reward_max)
    amount = int(base * multiplier)
    xp = max(3, amount // 8)
    return creature, amount, xp


def resolve_fight(attacker_strength: int, defender_strength: int, rng: random.Random | None = None) -> bool:
    """Pure: returns True if the attacker wins. Win probability follows the
    strength ratio (a much stronger attacker wins more often, but never
    with 100% certainty), clamped to [0.1, 0.9] so upsets stay possible."""
    rng = rng or random
    total = max(1, attacker_strength + defender_strength)
    win_chance = attacker_strength / total
    win_chance = min(0.9, max(0.1, win_chance))
    return rng.random() < win_chance


def fight_loot_amount(loser_balance: int, percent: float = FIGHT_LOOT_PERCENT, cap: int = FIGHT_LOOT_CAP) -> int:
    """Pure: how many coins change hands after a fight."""
    return min(cap, int(loser_balance * percent))


async def do_adventure(session: AsyncSession, user: User, cooldown_seconds: int,
                        reward_min: int = 50, reward_max: int = 300) -> tuple[bool, int, int, str, dt.timedelta | None, list[int]]:
    """Returns (succeeded, coins, xp, story, remaining_if_on_cooldown, levels_gained)."""
    remaining = _cooldown_check(user.last_adventure_at, cooldown_seconds)
    if remaining is not None:
        return False, 0, 0, "", remaining, []

    amount, xp, story = roll_adventure(reward_min, reward_max)
    user.balance += amount
    user.last_adventure_at = dt.datetime.now(dt.timezone.utc)
    levels_gained = apply_xp(user, xp)
    await session.flush()
    return True, amount, xp, story, None, levels_gained


async def do_hunt(session: AsyncSession, user: User, cooldown_seconds: int,
                   reward_min: int = 20, reward_max: int = 120) -> tuple[bool, str, int, int, dt.timedelta | None, list[int]]:
    """Returns (succeeded, creature, coins, xp, remaining_if_on_cooldown, levels_gained)."""
    remaining = _cooldown_check(user.last_hunt_at, cooldown_seconds)
    if remaining is not None:
        return False, "", 0, 0, remaining, []

    creature, amount, xp = roll_hunt(reward_min, reward_max)
    user.balance += amount
    user.last_hunt_at = dt.datetime.now(dt.timezone.utc)
    levels_gained = apply_xp(user, xp)
    await session.flush()
    return True, creature, amount, xp, None, levels_gained


async def do_fight(session: AsyncSession, attacker: User, defender: User,
                    cooldown_seconds: int) -> tuple[bool, bool, int, dt.timedelta | None]:
    """Returns (succeeded, attacker_won, coins_moved, remaining_if_on_cooldown)."""
    remaining = _cooldown_check(attacker.last_fight_at, cooldown_seconds)
    if remaining is not None:
        return False, False, 0, remaining

    attacker_won = resolve_fight(attacker.strength, defender.strength)
    loser = defender if attacker_won else attacker
    winner = attacker if attacker_won else defender
    amount = fight_loot_amount(loser.balance)

    loser.balance = max(0, loser.balance - amount)
    winner.balance += amount
    attacker.last_fight_at = dt.datetime.now(dt.timezone.utc)
    await session.flush()
    return True, attacker_won, amount, None
