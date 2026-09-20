from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import RestaurantStaffRole

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.order import Order
    from app.models.user import User


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    staff: Mapped[list[RestaurantStaff]] = relationship(back_populates="restaurant")
    menu_items: Mapped[list[MenuItem]] = relationship(back_populates="restaurant")
    orders: Mapped[list[Order]] = relationship(back_populates="restaurant")


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
