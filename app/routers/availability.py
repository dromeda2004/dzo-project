"""Opening hours and the pause toggle for a restaurant (epic4.task3).

Managers and owners set the weekly hours. Any staff member, including a shared kitchen
tablet, can pause and resume new orders, the same as the 86 toggle.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_restaurant_role
from app.core.database import get_db
from app.models import Restaurant, RestaurantHours
from app.models.enums import RestaurantStaffRole
from app.schemas.availability import AvailabilityOut, HoursUpdate, HoursWindow, PauseUpdate
from app.services.availability import is_accepting_orders, is_open, load_windows

router = APIRouter(prefix="/restaurants/{restaurant_id}", tags=["availability"])

editor = require_restaurant_role(RestaurantStaffRole.MANAGER)
any_staff = require_restaurant_role(RestaurantStaffRole.STAFF)


async def _availability(db: AsyncSession, restaurant: Restaurant) -> AvailabilityOut:
    windows = (await load_windows(db, [restaurant.id]))[restaurant.id]
    now = datetime.now(UTC)
    return AvailabilityOut(
        timezone=restaurant.timezone,
        hours=[HoursWindow.of(w) for w in windows],
        is_active=restaurant.is_active,
        orders_paused_at=restaurant.orders_paused_at,
        is_open_now=is_open(windows, restaurant.timezone, now),
        accepting_orders=is_accepting_orders(restaurant, windows, now),
    )


@router.get("/availability", response_model=AvailabilityOut)
async def get_availability(
    restaurant: Restaurant = Depends(any_staff), db: AsyncSession = Depends(get_db)
) -> AvailabilityOut:
    return await _availability(db, restaurant)


@router.put("/hours", response_model=AvailabilityOut)
async def replace_hours(
    payload: HoursUpdate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityOut:
    # Lock the restaurant so two concurrent saves can't interleave into a merged schedule.
    await db.execute(select(Restaurant.id).where(Restaurant.id == restaurant.id).with_for_update())
    await db.execute(delete(RestaurantHours).where(RestaurantHours.restaurant_id == restaurant.id))
    db.add_all(
        RestaurantHours(
            restaurant_id=restaurant.id,
            day_of_week=w.day.number,
            opens_at=w.opens_at,
            closes_at=w.closes_at,
        )
        for w in payload.hours
    )
    await db.commit()
    return await _availability(db, restaurant)


@router.put("/pause", response_model=AvailabilityOut)
async def set_pause(
    payload: PauseUpdate,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityOut:
    if payload.paused and restaurant.orders_paused_at is None:
        restaurant.orders_paused_at = datetime.now(UTC)
    elif not payload.paused:
        restaurant.orders_paused_at = None
    await db.commit()
    return await _availability(db, restaurant)
