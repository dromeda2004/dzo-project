"""Restaurant discovery and menus for customers (epic4.task4).

Any logged-in user can browse. Only active restaurants are visible; an inactive one is
404, the same as one that doesn't exist. Archived menu items never appear. Items the
restaurant has 86'd appear with `is_available: false`, so the menu doesn't reshuffle
every time something sells out.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import Restaurant
from app.schemas.food import (
    CategoryOut,
    MenuItemOut,
    MenuOut,
    RestaurantDetailOut,
    RestaurantSummaryOut,
)
from app.services.availability import load_windows
from app.services.menu import load_menu

router = APIRouter(
    prefix="/food/restaurants", tags=["food"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[RestaurantSummaryOut])
async def list_restaurants(db: AsyncSession = Depends(get_db)) -> list[RestaurantSummaryOut]:
    """Active restaurants, those taking orders right now first, then by name."""
    restaurants = list(
        await db.scalars(
            select(Restaurant)
            .where(Restaurant.is_active.is_(True))
            .order_by(Restaurant.name, Restaurant.id)
        )
    )
    windows = await load_windows(db, (r.id for r in restaurants))
    now = datetime.now(UTC)
    summaries = [RestaurantSummaryOut.build(r, windows[r.id], now) for r in restaurants]
    # Stable sort: within each group, the name order from the query is kept.
    return sorted(summaries, key=lambda s: not s.accepting_orders)


@router.get("/{restaurant_id}/menu", response_model=MenuOut)
async def get_menu(restaurant_id: int, db: AsyncSession = Depends(get_db)) -> MenuOut:
    """The restaurant (with its hours and whether it's taking orders) and its menu.
    Categories with no items are left out."""
    restaurant = await db.scalar(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active.is_(True))
    )
    if restaurant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    windows = (await load_windows(db, [restaurant.id]))[restaurant.id]
    categories, by_category = await load_menu(db, restaurant.id)
    return MenuOut(
        restaurant=RestaurantDetailOut.build(restaurant, windows, datetime.now(UTC)),
        categories=[
            CategoryOut(id=c.id, name=c.name, items=[MenuItemOut.of(i) for i in by_category[c.id]])
            for c in categories
            if by_category[c.id]
        ],
        uncategorized_items=[MenuItemOut.of(i) for i in by_category[None]],
    )
