from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import OrderStatus

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.driver import DriverProfile
    from app.models.menu import MenuItem
    from app.models.payment import Payment
    from app.models.promotion import Promotion
    from app.models.rating import Rating
    from app.models.restaurant import Restaurant
    from app.models.user import User


class Order(Base, TimestampMixin):
    """The core order record. Delivery fields are folded in directly rather than
    split into a separate `deliveries` table, since every delivery maps 1:1 to a
    Food order at launch — see docs/EPIC1_TRACKER.md epic1.task2 for the tradeoff.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("driver_profiles.id"), index=True)
    delivery_address_id: Mapped[int] = mapped_column(ForeignKey("addresses.id"))
    promotion_id: Mapped[int | None] = mapped_column(ForeignKey("promotions.id"))

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.PLACED, index=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tip: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    # Lifecycle timing — see docs/AGENTS_DZO.md section 1's seven-state order lifecycle.
    prep_time_estimate_minutes: Mapped[int | None] = mapped_column()
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proof_of_delivery: Mapped[str | None] = mapped_column(String(500))

    customer: Mapped[User] = relationship(back_populates="orders", foreign_keys=[customer_id])
    restaurant: Mapped[Restaurant] = relationship(back_populates="orders")
    driver: Mapped[DriverProfile | None] = relationship(back_populates="orders")
    delivery_address: Mapped[Address] = relationship()
    promotion: Mapped[Promotion | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")
    payment: Mapped[Payment | None] = relationship(back_populates="order", uselist=False)
    ratings: Mapped[list[Rating]] = relationship(back_populates="order")


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    quantity: Mapped[int] = mapped_column(default=1)
    price_at_order_time: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Snapshot of the chosen modifiers (name -> option/price at order time), since
    # menu_item_modifiers/modifier_options can change after the order is placed.
    selected_modifiers: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    order: Mapped[Order] = relationship(back_populates="items")
    menu_item: Mapped[MenuItem] = relationship(back_populates="order_items")
