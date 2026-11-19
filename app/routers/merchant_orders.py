"""The merchant order inbox (epic3.task6): any staff member can list their
restaurant's orders and open one. Merchants poll the list for new orders
(EPIC3_TRACKER.md open question 5)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_restaurant_role
from app.core.database import get_db
from app.models import DriverProfile, Order, OrderItem, Restaurant
from app.models.enums import OrderStatus, RestaurantStaffRole
from app.schemas.order import OrderDetailOut, OrderListOut, OrderSummaryOut

router = APIRouter(prefix="/restaurants/{restaurant_id}/orders", tags=["merchant orders"])

any_staff = require_restaurant_role(RestaurantStaffRole.STAFF)

# Shown by default: everything still in progress. Finished orders stay reachable by
# asking for their status explicitly.
FINISHED = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}
ACTIVE = [s for s in OrderStatus if s not in FINISHED]

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@router.get("", response_model=OrderListOut)
async def list_orders(
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
    status_: list[OrderStatus] | None = Query(
        None,
        alias="status",
        description="Repeat to filter by several statuses. Default: every status "
        "except delivered and cancelled.",
    ),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    before: int | None = Query(
        None,
        ge=1,
        description="Only orders older than this order id (the previous page's next_before).",
    ),
) -> OrderListOut:
    # Newest first by id, which increases with creation time. Paging by id rather than
    # offset means new orders arriving between polls don't shift the pages.
    query = (
        select(Order)
        .options(selectinload(Order.customer), selectinload(Order.items))
        .where(Order.restaurant_id == restaurant.id, Order.status.in_(status_ or ACTIVE))
        .order_by(Order.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        query = query.where(Order.id < before)
    orders = list(await db.scalars(query))

    has_more = len(orders) > limit
    page = orders[:limit]
    return OrderListOut(
        orders=[OrderSummaryOut.of(o) for o in page],
        next_before=page[-1].id if has_more else None,
    )


@router.get("/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: int,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    # Filtered on restaurant_id, so another restaurant's order is a 404.
    order = await db.scalar(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.delivery_address),
            selectinload(Order.items).selectinload(OrderItem.menu_item),
            selectinload(Order.driver).selectinload(DriverProfile.user),
        )
        .where(Order.id == order_id, Order.restaurant_id == restaurant.id)
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return OrderDetailOut.of(order)
