from __future__ import annotations

import datetime as dt
import random

import pytest

from modules.economy.service import get_or_create_user
from modules.rpg import service

pytestmark = pytest.mark.asyncio


async def test_adventure_grants_reward_and_respects_cooldown(session):
    user = await get_or_create_user(session, telegram_id=100, username="ash")

    ok, amount, xp, story, remaining, levels = await service.do_adventure(session, user, cooldown_seconds=1200)
    assert ok is True
    assert amount > 0
    assert xp > 0
    assert story
    assert user.last_adventure_at is not None

    ok2, _, _, _, remaining2, _ = await service.do_adventure(session, user, cooldown_seconds=1200)
    assert ok2 is False
    assert remaining2.total_seconds() > 0


async def test_hunt_grants_reward_and_respects_cooldown(session):
    user = await get_or_create_user(session, telegram_id=101, username="brock")

    ok, creature, amount, xp, remaining, levels = await service.do_hunt(session, user, cooldown_seconds=600)
    assert ok is True
    assert creature in [c for c, _ in service.HUNT_CREATURES]
    assert amount >= 0

    ok2, _, _, _, remaining2, _ = await service.do_hunt(session, user, cooldown_seconds=600)
    assert ok2 is False
    assert remaining2.total_seconds() > 0


async def test_fight_moves_coins_between_users_and_respects_cooldown(session):
    attacker = await get_or_create_user(session, telegram_id=102, username="misty")
    defender = await get_or_create_user(session, telegram_id=103, username="gary")
    attacker.balance = 1000
    defender.balance = 1000
    attacker.strength = 1000  # near-guaranteed win (clamped to 90%), deterministic-ish with seed below

    total_before = attacker.balance + defender.balance
    ok, attacker_won, amount, remaining = await service.do_fight(session, attacker, defender, cooldown_seconds=900)
    assert ok is True
    assert attacker.balance + defender.balance == total_before  # coins only move, never created/destroyed
    assert amount >= 0

    ok2, _, _, remaining2 = await service.do_fight(session, attacker, defender, cooldown_seconds=900)
    assert ok2 is False
    assert remaining2.total_seconds() > 0


async def test_fight_cooldown_is_per_attacker_not_global(session):
    attacker = await get_or_create_user(session, telegram_id=104, username="oak")
    defender = await get_or_create_user(session, telegram_id=105, username="jessie")
    third_party = await get_or_create_user(session, telegram_id=106, username="james")

    await service.do_fight(session, attacker, defender, cooldown_seconds=900)
    # A different attacker should not be affected by attacker's cooldown.
    ok, *_ = await service.do_fight(session, third_party, defender, cooldown_seconds=900)
    assert ok is True
