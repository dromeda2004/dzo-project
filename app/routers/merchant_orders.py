"""Merchant order endpoints. Any staff member at the restaurant (including a shared
kitchen-tablet account) and admins can use all of them.

- Inbox (epic3.task6): list the restaurant's orders and open one. Merchants poll
  the list for new orders (EPIC3_TRACKER.md open question 5).
- Acknowledge and cancel (epic3.task7), and the ready-time signal (epic3.task8),
  all through the task5 lifecycle guard.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_restaurant_role
from app.core.database import get_db
from app.models import DriverProfile, Order, OrderItem, Restaurant
from app.models.enums import OrderStatus, RestaurantStaffRole
from app.schemas.order import (
    AcknowledgeRequest,
    CancelRequest,
    OrderDetailOut,
    OrderListOut,
    OrderSummaryOut,
    ReadyTimeRequest,
)
from app.services.order_lifecycle import transition

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
    return OrderDetailOut.of(await _load_order(db, restaurant.id, order_id))


@router.post("/{order_id}/acknowledge", response_model=OrderDetailOut)
async def acknowledge_order(
    order_id: int,
    payload: AcknowledgeRequest,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    """Accept a Placed order with a prep-time estimate. It goes Placed -> Acknowledged
    -> Open for claim in one transaction, so drivers see it straight away (open
    question 2). Anything but a Placed order is a 409."""
    order = await _load_order(db, restaurant.id, order_id)
    await transition(
        db,
        order,
        OrderStatus.ACKNOWLEDGED,
        prep_time_estimate_minutes=payload.prep_time_estimate_minutes,
    )
    await transition(db, order, OrderStatus.OPEN_FOR_CLAIM)
    await db.commit()
    return OrderDetailOut.of(await _load_order(db, restaurant.id, order_id))


@router.post("/{order_id}/cancel", response_model=OrderDetailOut)
async def cancel_order(
    order_id: int,
    payload: CancelRequest,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    """Cancel an order the restaurant can't fulfil, with a reason. Only before a
    driver claims it (Placed, Acknowledged, Open for claim); after that it's an HQ
    action and this is a 409 (open question 1)."""
    order = await _load_order(db, restaurant.id, order_id)
    await transition(
        db,
        order,
        OrderStatus.CANCELLED,
        cancellation_reason=payload.reason,
        cancellation_note=payload.note,
    )
    await db.commit()
    return OrderDetailOut.of(await _load_order(db, restaurant.id, order_id))


@router.post("/{order_id}/ready-time", response_model=OrderDetailOut)
async def set_ready_time(
    order_id: int,
    payload: ReadyTimeRequest,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> OrderDetailOut:
    """Tell the claimed driver when to arrive: Claimed -> Ready-time set. Only once a
    driver has claimed the order (open question 3); anything else is a 409. Staff set
    it by hand (open question 4). Notifying the driver's phone is Epic 6, which reads
    the stored ready_time (open question 6)."""
    order = await _load_order(db, restaurant.id, order_id)
    await transition(
        db, order, OrderStatus.READY_TIME_SET, ready_time=payload.resolve(datetime.now(UTC))
    )
    await db.commit()
    return OrderDetailOut.of(await _load_order(db, restaurant.id, order_id))


async def _load_order(db: AsyncSession, restaurant_id: int, order_id: int) -> Order:
    # Filtered on restaurant_id, so another restaurant's order is a 404.
    order = await db.scalar(
        select(Order)
        .options(
            selectinload(Order.customer),
            selectinload(Order.delivery_address),
            selectinload(Order.items).selectinload(OrderItem.menu_item),
            selectinload(Order.driver).selectinload(DriverProfile.user),
        )
        .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
