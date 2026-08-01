from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MarketListing, User
from modules.shop.service import _get_inventory_row, get_item


async def create_listing(session: AsyncSession, seller: User, item_key: str, quantity: int,
                          price_per_unit: int) -> tuple[MarketListing | None, str | None]:
    """Returns (listing, error). error is one of: 'invalid_item', 'invalid_amount', 'not_owned'.
    Listed items are escrowed immediately (removed from the seller's inventory) so a
    seller can't sell the same item twice or spend/use it while it's listed."""
    if get_item(item_key) is None:
        return None, "invalid_item"
    if quantity <= 0 or price_per_unit <= 0:
        return None, "invalid_amount"

    row = await _get_inventory_row(session, seller, item_key)
    if row is None or row.quantity < quantity:
        return None, "not_owned"

    row.quantity -= quantity
    if row.quantity == 0:
        await session.delete(row)

    listing = MarketListing(
        seller_telegram_id=seller.telegram_id, item_key=item_key, quantity=quantity, price_per_unit=price_per_unit
    )
    session.add(listing)
    await session.flush()
    return listing, None


async def active_listings(session: AsyncSession, limit: int = 20) -> list[MarketListing]:
    result = await session.execute(
        select(MarketListing).where(MarketListing.is_active.is_(True)).order_by(MarketListing.created_at.desc()).limit(limit)
    )
    return list(result.scalars())


async def buy_listing(session: AsyncSession, buyer: User, listing_id: int) -> tuple[MarketListing | None, str | None]:
    """Returns (listing, error). error is one of: 'not_found', 'self_purchase', 'insufficient_funds'.
    Full-listing purchase only (buys the whole stack at once) to keep escrow bookkeeping simple."""
    listing = await session.get(MarketListing, listing_id)
    if listing is None or not listing.is_active:
        return None, "not_found"
    if listing.seller_telegram_id == buyer.telegram_id:
        return None, "self_purchase"

    total_cost = listing.quantity * listing.price_per_unit
    if buyer.balance < total_cost:
        return None, "insufficient_funds"

    buyer.balance -= total_cost

    seller_result = await session.execute(select(User).where(User.telegram_id == listing.seller_telegram_id))
    seller = seller_result.scalar_one_or_none()
    if seller is not None:
        seller.balance += total_cost

    buyer_row = await _get_inventory_row(session, buyer, listing.item_key)
    if buyer_row is None:
        from database.models import InventoryItem

        buyer_row = InventoryItem(user_id=buyer.id, item_key=listing.item_key, quantity=listing.quantity)
        session.add(buyer_row)
    else:
        buyer_row.quantity += listing.quantity

    listing.is_active = False
    listing.sold_at = dt.datetime.now(dt.timezone.utc)
    await session.flush()
    return listing, None


async def cancel_listing(session: AsyncSession, seller: User, listing_id: int) -> tuple[MarketListing | None, str | None]:
    """Returns (listing, error). error is one of: 'not_found', 'not_owner'. Returns the
    escrowed items back to the seller's inventory."""
    listing = await session.get(MarketListing, listing_id)
    if listing is None or not listing.is_active:
        return None, "not_found"
    if listing.seller_telegram_id != seller.telegram_id:
        return None, "not_owner"

    row = await _get_inventory_row(session, seller, listing.item_key)
    if row is None:
        from database.models import InventoryItem

        row = InventoryItem(user_id=seller.id, item_key=listing.item_key, quantity=listing.quantity)
        session.add(row)
    else:
        row.quantity += listing.quantity

    listing.is_active = False
    await session.flush()
    return listing, None
