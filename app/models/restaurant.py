from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import RestaurantStaffRole

if TYPE_CHECKING:
    from app.models.menu import MenuCategory, MenuItem
    from app.models.order import Order
    from app.models.user import User


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Set while staff have paused new orders (e.g. a busy night); null otherwise.
    orders_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    staff: Mapped[list[RestaurantStaff]] = relationship(back_populates="restaurant")
    menu_categories: Mapped[list[MenuCategory]] = relationship(back_populates="restaurant")
    menu_items: Mapped[list[MenuItem]] = relationship(back_populates="restaurant")
    orders: Mapped[list[Order]] = relationship(back_populates="restaurant")
    hours: Mapped[list[RestaurantHours]] = relationship(
        back_populates="restaurant",
        order_by="(RestaurantHours.day_of_week, RestaurantHours.opens_at)",
        passive_deletes=True,
    )


class RestaurantHours(Base, TimestampMixin):
    """One opening window, in the restaurant's own timezone (epic4.task3).

    A day can have several windows (e.g. lunch and dinner). A window whose `closes_at`
    is at or before `opens_at` runs past midnight into the next day, so 17:00-01:00 is
    stored on the day it opens; equal times mean open for 24 hours.
    """

    __tablename__ = "restaurant_hours"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_restaurant_hours_day_of_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    # Monday = 0 ... Sunday = 6, matching Python's date.weekday().
    day_of_week: Mapped[int] = mapped_column(SmallInteger)
    opens_at: Mapped[time] = mapped_column(Time)
    closes_at: Mapped[time] = mapped_column(Time)

    restaurant: Mapped[Restaurant] = relationship(back_populates="hours")


class RestaurantStaff(Base, TimestampMixin):
    """Join table: which users work at which restaurant, and in what role."""

    __tablename__ = "restaurant_staff"
    __table_args__ = (
        UniqueConstraint("user_id", "restaurant_id", name="uq_restaurant_staff_user_restaurant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    role: Mapped[RestaurantStaffRole] = mapped_column(
        Enum(RestaurantStaffRole, name="restaurant_staff_role")
    )

    user: Mapped[User] = relationship(back_populates="restaurant_staff_memberships")
    restaurant: Mapped[Restaurant] = relationship(back_populates="staff")
