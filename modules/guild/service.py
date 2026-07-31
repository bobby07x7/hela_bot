from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Guild, GuildMember, User


async def get_membership(session: AsyncSession, telegram_id: int) -> GuildMember | None:
    result = await session.execute(select(GuildMember).where(GuildMember.member_telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_guild_by_name(session: AsyncSession, name: str) -> Guild | None:
    result = await session.execute(select(Guild).where(func.lower(Guild.name) == name.lower()))
    return result.scalar_one_or_none()


async def create_guild(session: AsyncSession, owner_telegram_id: int, name: str) -> tuple[Guild | None, str | None]:
    """Returns (guild, error). error is one of: 'name_taken', 'already_in_guild'."""
    if await get_membership(session, owner_telegram_id) is not None:
        return None, "already_in_guild"
    if await get_guild_by_name(session, name) is not None:
        return None, "name_taken"

    guild = Guild(name=name, owner_telegram_id=owner_telegram_id)
    session.add(guild)
    await session.flush()
    session.add(GuildMember(guild_id=guild.id, member_telegram_id=owner_telegram_id, role="owner"))
    await session.flush()
    return guild, None


async def join_guild(session: AsyncSession, telegram_id: int, name: str) -> tuple[Guild | None, str | None]:
    """Returns (guild, error). error is one of: 'already_in_guild', 'not_found'."""
    if await get_membership(session, telegram_id) is not None:
        return None, "already_in_guild"
    guild = await get_guild_by_name(session, name)
    if guild is None:
        return None, "not_found"

    session.add(GuildMember(guild_id=guild.id, member_telegram_id=telegram_id, role="member"))
    await session.flush()
    return guild, None


async def leave_guild(session: AsyncSession, telegram_id: int) -> tuple[Guild | None, str | None]:
    """Returns (guild, error). error is one of: 'not_in_guild', 'is_owner'."""
    membership = await get_membership(session, telegram_id)
    if membership is None:
        return None, "not_in_guild"
    if membership.role == "owner":
        return None, "is_owner"

    guild = await session.get(Guild, membership.guild_id)
    await session.delete(membership)
    await session.flush()
    return guild, None


async def donate(session: AsyncSession, user: User, telegram_id: int, amount: int) -> tuple[Guild | None, str | None]:
    """Returns (guild, error). error is one of: 'not_in_guild', 'insufficient_funds'."""
    if amount <= 0 or user.balance < amount:
        return None, "insufficient_funds"
    membership = await get_membership(session, telegram_id)
    if membership is None:
        return None, "not_in_guild"

    guild = await session.get(Guild, membership.guild_id)
    user.balance -= amount
    guild.bank += amount
    membership.contributed += amount
    await session.flush()
    return guild, None


async def kick_member(session: AsyncSession, owner_telegram_id: int, target_telegram_id: int) -> tuple[bool, str | None]:
    """Returns (success, error). error is one of: 'not_permitted', 'target_not_member'."""
    owner_membership = await get_membership(session, owner_telegram_id)
    if owner_membership is None or owner_membership.role != "owner":
        return False, "not_permitted"

    target_membership = await get_membership(session, target_telegram_id)
    if target_membership is None or target_membership.guild_id != owner_membership.guild_id:
        return False, "target_not_member"

    await session.delete(target_membership)
    await session.flush()
    return True, None


async def member_count(session: AsyncSession, guild_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(GuildMember).where(GuildMember.guild_id == guild_id))
    return result.scalar_one()


async def list_guilds(session: AsyncSession, limit: int = 20) -> list[Guild]:
    result = await session.execute(select(Guild).order_by(Guild.bank.desc()).limit(limit))
    return list(result.scalars())
