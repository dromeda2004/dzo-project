import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from itertools import product

import pytest
import pytest_asyncio
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.error_handlers import illegal_transition_handler
from app.models import Address, DriverProfile, Order, Restaurant, User
from app.models.enums import CancellationReason, OrderStatus
from app.services.order_lifecycle import (
    IllegalTransitionError,
    InvalidTransitionDataError,
    is_allowed,
    transition,
)
from tests.factories import create_driver, create_order

S = OrderStatus
NOW = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)

# Written out independently of ALLOWED_TRANSITIONS, from AGENTS_DZO.md section 1 and
# EPIC3_TRACKER.md open question 1, so a change to the guard has to match this.
DELIVERY_PATH = [
    S.PLACED,
    S.ACKNOWLEDGED,
    S.OPEN_FOR_CLAIM,
    S.CLAIMED,
    S.READY_TIME_SET,
    S.PICKED_UP,
    S.DELIVERED,
]
EXPECTED = {(a, b) for a, b in zip(DELIVERY_PATH, DELIVERY_PATH[1:], strict=False)} | {
    (S.PLACED, S.CANCELLED),
    (S.ACKNOWLEDGED, S.CANCELLED),
    (S.OPEN_FOR_CLAIM, S.CANCELLED),
}


@pytest.mark.parametrize(("current", "target"), list(product(S, S)))
def test_allowed_transitions_are_exactly_the_lifecycle(current: S, target: S) -> None:
    assert is_allowed(current, target) == ((current, target) in EXPECTED)


async def test_walks_the_full_delivery_path(db_session: AsyncSession) -> None:
    order = await create_order(db_session)
    driver = await create_driver(db_session)
    ready = NOW + timedelta(minutes=20)

    await transition(db_session, order, S.ACKNOWLEDGED, now=NOW, prep_time_estimate_minutes=25)
    assert (order.status, order.acknowledged_at, order.prep_time_estimate_minutes) == (
        S.ACKNOWLEDGED,
        NOW,
        25,
    )

    await transition(db_session, order, S.OPEN_FOR_CLAIM, now=NOW)
    assert order.status == S.OPEN_FOR_CLAIM

    await transition(db_session, order, S.CLAIMED, now=NOW, driver_id=driver.id)
    assert (order.status, order.claimed_at, order.driver_id) == (S.CLAIMED, NOW, driver.id)

    await transition(db_session, order, S.READY_TIME_SET, ready_time=ready)
    assert (order.status, order.ready_time) == (S.READY_TIME_SET, ready)

    await transition(db_session, order, S.PICKED_UP, now=NOW)
    assert (order.status, order.picked_up_at) == (S.PICKED_UP, NOW)

    await transition(db_session, order, S.DELIVERED, now=NOW, proof_of_delivery="photo.jpg")
    assert (order.status, order.delivered_at, order.proof_of_delivery) == (
        S.DELIVERED,
        NOW,
        "photo.jpg",
    )


@pytest.mark.parametrize("start", [S.PLACED, S.ACKNOWLEDGED, S.OPEN_FOR_CLAIM])
async def test_cancel_before_claim(db_session: AsyncSession, start: S) -> None:
    order = await create_order(db_session, status=start)

    await transition(
        db_session,
        order,
        S.CANCELLED,
        now=NOW,
        cancellation_reason=CancellationReason.ITEM_UNAVAILABLE,
        cancellation_note="Out of fish",
    )

    assert order.status == S.CANCELLED
    assert order.cancelled_at == NOW
    assert order.cancellation_reason == CancellationReason.ITEM_UNAVAILABLE
    assert order.cancellation_note == "Out of fish"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (S.PLACED, S.OPEN_FOR_CLAIM),  # skip
        (S.PLACED, S.DELIVERED),  # skip to the end
        (S.ACKNOWLEDGED, S.CLAIMED),  # skip
        (S.CLAIMED, S.ACKNOWLEDGED),  # backwards
        (S.PICKED_UP, S.READY_TIME_SET),  # backwards
        (S.ACKNOWLEDGED, S.ACKNOWLEDGED),  # repeat
        (S.DELIVERED, S.DELIVERED),  # repeat
        (S.CLAIMED, S.CANCELLED),  # cancel after a driver claimed
        (S.READY_TIME_SET, S.CANCELLED),
        (S.DELIVERED, S.PLACED),  # out of a terminal state
    ],
)
async def test_illegal_transitions_are_rejected(
    db_session: AsyncSession, start: S, target: S
) -> None:
    order = await create_order(db_session, status=start)

    with pytest.raises(IllegalTransitionError, match=f"from {start.value} to {target.value}"):
        # Data is checked after legality, so these don't need valid data.
        await transition(db_session, order, target)

    await db_session.refresh(order)
    assert order.status == start


async def test_nothing_leaves_cancelled(db_session: AsyncSession) -> None:
    order = await create_order(db_session)
    await transition(db_session, order, S.CANCELLED, cancellation_reason=CancellationReason.CLOSING)

    for target in S:
        with pytest.raises(IllegalTransitionError):
            await transition(db_session, order, target)


@pytest.mark.parametrize(
    ("start", "target", "data", "message"),
    [
        (S.PLACED, S.ACKNOWLEDGED, {}, "requires"),
        (S.PLACED, S.ACKNOWLEDGED, {"prep_time_estimate_minutes": 0}, "positive"),
        (S.OPEN_FOR_CLAIM, S.CLAIMED, {}, "requires"),
        (S.CLAIMED, S.READY_TIME_SET, {}, "requires"),
        (S.CLAIMED, S.READY_TIME_SET, {"ready_time": datetime(2026, 11, 15, 18)}, "aware"),
        (S.PLACED, S.CANCELLED, {}, "requires"),
        (S.PLACED, S.CANCELLED, {"cancellation_reason": CancellationReason.OTHER}, "note"),
        (
            S.PLACED,
            S.CANCELLED,
            {"cancellation_reason": CancellationReason.OTHER, "cancellation_note": "  "},
            "note",
        ),
        # Fields that belong to another state are refused.
        (
            S.PLACED,
            S.CANCELLED,
            {"cancellation_reason": CancellationReason.TOO_BUSY, "driver_id": 1},
            "doesn't take",
        ),
        (S.PLACED, S.ACKNOWLEDGED, {"prep_time_estimate_minutes": 10, "ready_time": NOW}, "take"),
    ],
)
async def test_wrong_data_for_the_target_state_is_rejected(
    db_session: AsyncSession, start: S, target: S, data: dict, message: str
) -> None:
    order = await create_order(db_session, status=start)

    with pytest.raises(InvalidTransitionDataError, match=message):
        await transition(db_session, order, target, **data)

    await db_session.refresh(order)
    assert order.status == start


async def test_other_reason_with_a_note_is_accepted(db_session: AsyncSession) -> None:
    order = await create_order(db_session)
    await transition(
        db_session,
        order,
        S.CANCELLED,
        cancellation_reason=CancellationReason.OTHER,
        cancellation_note="Gas leak",
    )
    assert order.status == S.CANCELLED


async def test_stale_order_is_rejected(db_session: AsyncSession) -> None:
    """Another request moved the order after this caller loaded it."""
    order = await create_order(db_session)
    await db_session.execute(
        update(Order)
        .where(Order.id == order.id)
        .values(status=S.ACKNOWLEDGED, acknowledged_at=NOW, prep_time_estimate_minutes=10)
        .execution_options(synchronize_session=False)
    )
    assert order.status == S.PLACED  # this caller's copy is now out of date

    with pytest.raises(IllegalTransitionError, match="changed by another request"):
        await transition(db_session, order, S.ACKNOWLEDGED, prep_time_estimate_minutes=10)
    assert order.status == S.ACKNOWLEDGED


async def test_database_rejects_a_cancelled_order_without_a_reason(
    db_session: AsyncSession,
) -> None:
    order = await create_order(db_session)
    with pytest.raises(IntegrityError, match="ck_orders_cancellation_complete"):
        await db_session.execute(
            update(Order).where(Order.id == order.id).values(status=S.CANCELLED)
        )


async def test_illegal_transition_is_a_409_in_the_error_envelope() -> None:
    response = await illegal_transition_handler(
        None,  # type: ignore[arg-type]
        IllegalTransitionError("Order 1 can't move from placed to delivered"),
    )
    assert response.status_code == 409
    assert json.loads(bytes(response.body)) == {
        "error": {
            "code": "conflict",
            "message": "Order 1 can't move from placed to delivered",
            "fields": None,
        }
    }


# --- Real concurrency: two connections, committed data ---------------------------


@pytest_asyncio.fixture
async def committed_open_order() -> AsyncGenerator[tuple[int, int, int]]:
    """An Open-for-claim order and two drivers, committed so two separate connections
    can see them, then deleted afterwards (tests share the dev database)."""
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        order = await create_order(
            s, status=S.OPEN_FOR_CLAIM, customer_email="race-customer@example.com"
        )
        d1 = await create_driver(s, email="race-driver-1@example.com")
        d2 = await create_driver(s, email="race-driver-2@example.com")
        await s.commit()
        ids = (order.id, d1.id, d2.id)
        restaurant_id, address_id = order.restaurant_id, order.delivery_address_id
    try:
        yield ids
    finally:
        async with AsyncSession(engine) as s:
            await s.execute(delete(Order).where(Order.id == ids[0]))
            await s.execute(delete(DriverProfile).where(DriverProfile.id.in_(ids[1:])))
            await s.execute(delete(Address).where(Address.id == address_id))
            await s.execute(delete(Restaurant).where(Restaurant.id == restaurant_id))
            await s.execute(delete(User).where(User.email.like("race-%@example.com")))
            await s.commit()
        await engine.dispose()


async def test_two_drivers_claiming_at_once_only_one_wins(
    committed_open_order: tuple[int, int, int],
) -> None:
    order_id, driver_1, driver_2 = committed_open_order
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with (
            AsyncSession(engine, expire_on_commit=False) as first,
            AsyncSession(engine, expire_on_commit=False) as second,
        ):
            # Both load the order while it's still Open for claim.
            order_a = await first.get(Order, order_id)
            order_b = await second.get(Order, order_id)
            assert order_a is not None and order_b is not None

            await transition(first, order_a, S.CLAIMED, driver_id=driver_1)  # holds the row lock
            racing = asyncio.create_task(transition(second, order_b, S.CLAIMED, driver_id=driver_2))
            await asyncio.sleep(0.3)
            assert not racing.done()  # blocked behind the first claim

            await first.commit()
            with pytest.raises(IllegalTransitionError, match="changed by another request"):
                await racing
            await second.rollback()

        async with AsyncSession(engine) as check:
            final = await check.get(Order, order_id)
            assert final is not None
            assert (final.status, final.driver_id) == (S.CLAIMED, driver_1)
    finally:
        await engine.dispose()
