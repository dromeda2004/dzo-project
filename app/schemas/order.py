"""Order schemas for the merchant inbox (epic3.task6).

Customer details are limited to what the restaurant needs to make and hand over the
order: a first name and the delivery address. No email, phone, or full name
(EPIC3_TRACKER.md epic3.task6).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.models import Address, DriverProfile, Order, OrderItem, User
from app.models.enums import CancellationReason, OrderStatus


def first_name(user: User) -> str:
    parts = user.full_name.split()
    return parts[0] if parts else ""


# --- Actions (epic3.task7) -------------------------------------------------------

MAX_PREP_TIME_MINUTES = 180


class AcknowledgeRequest(BaseModel):
    prep_time_estimate_minutes: int = Field(ge=1, le=MAX_PREP_TIME_MINUTES)


class CancelRequest(BaseModel):
    reason: CancellationReason
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _note_for_other(self) -> Self:
        self.note = (self.note or "").strip() or None
        if self.reason == CancellationReason.OTHER and self.note is None:
            raise ValueError("A note is required when the reason is 'other'")
        return self


# --- Reads -----------------------------------------------------------------------


class CustomerOut(BaseModel):
    first_name: str


class DeliveryAddressOut(BaseModel):
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    delivery_instructions: str | None

    @classmethod
    def of(cls, address: Address) -> "DeliveryAddressOut":
        return cls(
            line1=address.line1,
            line2=address.line2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            delivery_instructions=address.delivery_instructions,
        )


class DriverOut(BaseModel):
    id: int
    first_name: str
    vehicle_description: str | None

    @classmethod
    def of(cls, driver: DriverProfile) -> "DriverOut":
        return cls(
            id=driver.id,
            first_name=first_name(driver.user),
            vehicle_description=driver.vehicle_description,
        )


class OrderItemOut(BaseModel):
    id: int
    menu_item_id: int
    # The menu item's current name. Prices and modifiers are snapshotted at order
    # time; names aren't yet, so a rename shows up here.
    name: str
    quantity: int
    # Unit price including modifiers, as charged. Not today's menu price.
    price_at_order_time: Decimal
    line_total: Decimal
    selected_modifiers: dict[str, Any] | None

    @classmethod
    def of(cls, item: OrderItem) -> "OrderItemOut":
        return cls(
            id=item.id,
            menu_item_id=item.menu_item_id,
            name=item.menu_item.name,
            quantity=item.quantity,
            price_at_order_time=item.price_at_order_time,
            line_total=item.price_at_order_time * item.quantity,
            selected_modifiers=item.selected_modifiers,
        )


class OrderSummaryOut(BaseModel):
    """One row of the inbox."""

    id: int
    status: OrderStatus
    created_at: datetime
    customer_first_name: str
    item_count: int
    subtotal: Decimal
    prep_time_estimate_minutes: int | None
    ready_time: datetime | None

    @classmethod
    def of(cls, order: Order) -> "OrderSummaryOut":
        return cls(
            id=order.id,
            status=order.status,
            created_at=order.created_at,
            customer_first_name=first_name(order.customer),
            item_count=sum(i.quantity for i in order.items),
            subtotal=order.subtotal,
            prep_time_estimate_minutes=order.prep_time_estimate_minutes,
            ready_time=order.ready_time,
        )


class OrderListOut(BaseModel):
    orders: list[OrderSummaryOut]
    # Pass as `before` to get the next (older) page; null when there are no more.
    next_before: int | None


class OrderDetailOut(BaseModel):
    id: int
    status: OrderStatus
    created_at: datetime
    customer: CustomerOut
    delivery_address: DeliveryAddressOut
    items: list[OrderItemOut]
    subtotal: Decimal
    tip: Decimal
    prep_time_estimate_minutes: int | None
    acknowledged_at: datetime | None
    claimed_at: datetime | None
    ready_time: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    driver: DriverOut | None
    cancelled_at: datetime | None
    cancellation_reason: CancellationReason | None
    cancellation_note: str | None

    @classmethod
    def of(cls, order: Order) -> "OrderDetailOut":
        return cls(
            id=order.id,
            status=order.status,
            created_at=order.created_at,
            customer=CustomerOut(first_name=first_name(order.customer)),
            delivery_address=DeliveryAddressOut.of(order.delivery_address),
            items=[OrderItemOut.of(i) for i in sorted(order.items, key=lambda i: i.id)],
            subtotal=order.subtotal,
            tip=order.tip,
            prep_time_estimate_minutes=order.prep_time_estimate_minutes,
            acknowledged_at=order.acknowledged_at,
            claimed_at=order.claimed_at,
            ready_time=order.ready_time,
            picked_up_at=order.picked_up_at,
            delivered_at=order.delivered_at,
            driver=DriverOut.of(order.driver) if order.driver else None,
            cancelled_at=order.cancelled_at,
            cancellation_reason=order.cancellation_reason,
            cancellation_note=order.cancellation_note,
        )
