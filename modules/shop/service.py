from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import InventoryItem, User
from modules.economy.service import apply_xp

# Static catalog. Real deployments could move this to a DB table if they
# want owners to add items live - this mirrors the same shape either way,
# so that migration is a small, contained change.
CATALOG: dict[str, dict] = {
    "sword": {"name": "Iron Sword", "price": 200, "sell_price": 100, "category": "weapon", "usable": False},
    "shield": {"name": "Wooden Shield", "price": 150, "sell_price": 75, "category": "armor", "usable": False},
    "potion": {"name": "Health Potion", "price": 50, "sell_price": 20, "category": "consumable",
               "usable": True, "effect": "heal", "heal_amount": 50},
    "xp_scroll": {"name": "XP Scroll", "price": 300, "sell_price": 120, "category": "consumable",
                  "usable": True, "effect": "xp", "xp_amount": 100},
    "fishing_rod": {"name": "Fishing Rod", "price": 120, "sell_price": 50, "category": "tool", "usable": False},
    "lucky_coin": {"name": "Lucky Coin", "price": 500, "sell_price": 200, "category": "trinket", "usable": False},
}


def get_item(item_key: str) -> dict | None:
    return CATALOG.get(item_key)


def format_catalog() -> list[str]:
    lines = []
    for key, item in CATALOG.items():
        lines.append(f"`{key}` - {item['name']} - {item['price']} coins")
    return lines


async def _get_inventory_row(session: AsyncSession, user: User, item_key: str) -> InventoryItem | None:
    result = await session.execute(
        select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.item_key == item_key)
    )
    return result.scalar_one_or_none()


async def buy_item(session: AsyncSession, user: User, item_key: str, quantity: int) -> tuple[bool, int]:
    """Returns (success, total_cost)."""
    item = get_item(item_key)
    if item is None or quantity <= 0:
        return False, 0
    total_cost = item["price"] * quantity
    if user.balance < total_cost:
        return False, total_cost

    user.balance -= total_cost
    row = await _get_inventory_row(session, user, item_key)
    if row is None:
        row = InventoryItem(user_id=user.id, item_key=item_key, quantity=quantity)
        session.add(row)
    else:
        row.quantity += quantity
    await session.flush()
    return True, total_cost


async def sell_item(session: AsyncSession, user: User, item_key: str, quantity: int) -> tuple[bool, int]:
    """Returns (success, total_received)."""
    item = get_item(item_key)
    if item is None or quantity <= 0:
        return False, 0

    row = await _get_inventory_row(session, user, item_key)
    if row is None or row.quantity < quantity:
        return False, 0

    total_received = item["sell_price"] * quantity
    row.quantity -= quantity
    user.balance += total_received
    if row.quantity == 0:
        await session.delete(row)
    await session.flush()
    return True, total_received


async def use_item(session: AsyncSession, user: User, item_key: str) -> tuple[bool, str]:
    """Returns (success, effect_description). Consumes exactly one unit."""
    item = get_item(item_key)
    if item is None or not item.get("usable"):
        return False, ""

    row = await _get_inventory_row(session, user, item_key)
    if row is None or row.quantity < 1:
        return False, ""

    effect = item["effect"]
    if effect == "heal":
        healed = min(item["heal_amount"], user.max_hp - user.hp)
        user.hp = min(user.max_hp, user.hp + item["heal_amount"])
        description = f"restored {healed} HP ({user.hp}/{user.max_hp})"
    elif effect == "xp":
        apply_xp(user, item["xp_amount"])
        description = f"gained {item['xp_amount']} XP"
    else:
        description = "nothing happened"

    row.quantity -= 1
    if row.quantity == 0:
        await session.delete(row)
    await session.flush()
    return True, description
