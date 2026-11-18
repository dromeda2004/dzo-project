"""The one place an order's status changes (epic3.task5).

Every product that moves an order (Biz acknowledging it, Ride claiming it, HQ
stepping in) calls `transition()`. It only allows the lifecycle in
docs/AGENTS_DZO.md section 1, one step at a time, plus cancellation from the first
three states, and records the timestamp for the state it enters. Anything else
raises `IllegalTransitionError`, which the API returns as 409.

Concurrency: the UPDATE only matches if the order is still in the status the caller
loaded. If another request moved it first (two drivers claiming at once, a
restaurant cancelling while a driver claims), Postgres makes the second UPDATE wait
for the first to commit, then re-checks the WHERE clause, matches nothing, and the
second caller gets a 409. No state is skipped and no claim is lost silently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.models.enums import CancellationReason, OrderStatus

S = OrderStatus

# Delivery path. Pickup orders get their own path when pickup comes back
# (EPIC3_TRACKER.md open question 7).
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.PLACED: frozenset({S.ACKNOWLEDGED, S.CANCELLED}),
    S.ACKNOWLEDGED: frozenset({S.OPEN_FOR_CLAIM, S.CANCELLED}),
    S.OPEN_FOR_CLAIM: frozenset({S.CLAIMED, S.CANCELLED}),
    S.CLAIMED: frozenset({S.READY_TIME_SET}),
    S.READY_TIME_SET: frozenset({S.PICKED_UP}),
    S.PICKED_UP: frozenset({S.DELIVERED}),
    S.DELIVERED: frozenset(),
    S.CANCELLED: frozenset(),
}

# Data each target state takes. Required fields must be given; anything not listed
# for the target is rejected, so a caller can't, say, set a driver while cancelling.
_REQUIRED: dict[OrderStatus, frozenset[str]] = {
    S.ACKNOWLEDGED: frozenset({"prep_time_estimate_minutes"}),
    S.CLAIMED: frozenset({"driver_id"}),
    S.READY_TIME_SET: frozenset({"ready_time"}),
    S.CANCELLED: frozenset({"cancellation_reason"}),
}
_OPTIONAL: dict[OrderStatus, frozenset[str]] = {
    S.DELIVERED: frozenset({"proof_of_delivery"}),
    S.CANCELLED: frozenset({"cancellation_note"}),
}
# The timestamp column each state records when it's entered. Open for claim has
# none: it happens in the same transaction as acknowledging (open question 2).
_TIMESTAMP: dict[OrderStatus, str] = {
    S.ACKNOWLEDGED: "acknowledged_at",
    S.CLAIMED: "claimed_at",
    S.PICKED_UP: "picked_up_at",
    S.DELIVERED: "delivered_at",
    S.CANCELLED: "cancelled_at",
}


class IllegalTransitionError(Exception):
    """The requested status change isn't allowed from the order's current state, or
    the order changed underneath the caller. Returned to API clients as 409."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidTransitionDataError(ValueError):
    """The caller passed the wrong data for the target state. A programming error in
    the caller, not something a client can trigger, since routers validate input."""


def is_allowed(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def _check_data(target: OrderStatus, data: dict[str, Any]) -> None:
    required = _REQUIRED.get(target, frozenset())
    allowed = required | _OPTIONAL.get(target, frozenset())
    given = {k for k, v in data.items() if v is not None}
    if missing := required - given:
        raise InvalidTransitionDataError(f"{target.value} requires {sorted(missing)}")
    if extra := given - allowed:
        raise InvalidTransitionDataError(f"{target.value} doesn't take {sorted(extra)}")

    if target == S.ACKNOWLEDGED and data["prep_time_estimate_minutes"] <= 0:
        raise InvalidTransitionDataError("prep_time_estimate_minutes must be positive")
    if target == S.READY_TIME_SET and data["ready_time"].tzinfo is None:
        raise InvalidTransitionDataError("ready_time must be timezone-aware")
    if target == S.CANCELLED:
        reason = CancellationReason(data["cancellation_reason"])
        note = (data.get("cancellation_note") or "").strip()
        if reason == CancellationReason.OTHER and not note:
            raise InvalidTransitionDataError("cancellation_reason 'other' requires a note")


async def transition(
    session: AsyncSession,
    order: Order,
    target: OrderStatus,
    *,
    now: datetime | None = None,
    **data: Any,
) -> Order:
    """Move `order` from its current status to `target`, recording the matching
    timestamp and `data` (see _REQUIRED/_OPTIONAL). Flushes but doesn't commit, so a
    caller can make several transitions atomically (acknowledge + open for claim).

    Raises IllegalTransitionError if the move isn't allowed, or if the order is no
    longer in the status `order` was loaded with.
    """
    current = order.status
    if not is_allowed(current, target):
        raise IllegalTransitionError(
            f"Order {order.id} can't move from {current.value} to {target.value}"
        )
    _check_data(target, data)

    values: dict[str, Any] = {k: v for k, v in data.items() if v is not None}
    values["status"] = target
    if column := _TIMESTAMP.get(target):
        values[column] = now or datetime.now(UTC)

    # Make sure pending changes to this order are in the DB before the conditional
    # UPDATE compares against it.
    await session.flush()
    result = await session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == current)
        .values(**values)
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if result.scalar_one_or_none() is None:
        await session.refresh(order, attribute_names=["status"])
        raise IllegalTransitionError(
            f"Order {order.id} was changed by another request "
            f"(now {order.status.value}); reload it and try again"
        )
    await session.refresh(order)
    return order
