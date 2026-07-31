from __future__ import annotations

import pytest

from modules.economy.service import get_or_create_user
from modules.guild import service

pytestmark = pytest.mark.asyncio


async def test_create_guild_and_prevent_duplicate_name(session):
    guild, error = await service.create_guild(session, owner_telegram_id=400, name="Dragons")
    assert error is None
    assert guild.name == "Dragons"

    dup, error2 = await service.create_guild(session, owner_telegram_id=401, name="Dragons")
    assert dup is None
    assert error2 == "name_taken"


async def test_owner_cannot_create_second_guild(session):
    await service.create_guild(session, owner_telegram_id=402, name="Wolves")
    second, error = await service.create_guild(session, owner_telegram_id=402, name="Eagles")
    assert second is None
    assert error == "already_in_guild"


async def test_join_and_leave_guild(session):
    await service.create_guild(session, owner_telegram_id=403, name="Phoenixes")
    guild, error = await service.join_guild(session, telegram_id=404, name="Phoenixes")
    assert error is None
    assert guild.name == "Phoenixes"

    left_guild, error2 = await service.leave_guild(session, telegram_id=404)
    assert error2 is None
    assert left_guild.name == "Phoenixes"


async def test_owner_cannot_leave_own_guild(session):
    await service.create_guild(session, owner_telegram_id=405, name="Titans")
    guild, error = await service.leave_guild(session, telegram_id=405)
    assert guild is None
    assert error == "is_owner"


async def test_donate_moves_coins_to_guild_bank(session):
    await service.create_guild(session, owner_telegram_id=406, name="Sharks")
    user = await get_or_create_user(session, telegram_id=406, username="sharkowner")
    user.balance = 500

    guild, error = await service.donate(session, user, 406, 200)
    assert error is None
    assert guild.bank == 200
    assert user.balance == 300


async def test_kick_requires_owner_role(session):
    await service.create_guild(session, owner_telegram_id=407, name="Ravens")
    await service.join_guild(session, telegram_id=408, name="Ravens")

    ok, error = await service.kick_member(session, owner_telegram_id=408, target_telegram_id=407)
    assert ok is False
    assert error == "not_permitted"  # 408 is a member, not the owner

    ok2, error2 = await service.kick_member(session, owner_telegram_id=407, target_telegram_id=408)
    assert ok2 is True
    assert error2 is None
