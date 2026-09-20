from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.driver import DriverProfile
    from app.models.order import Order
    from app.models.restaurant import RestaurantStaff


class User(Base, TimestampMixin):
    """Shared identity for every role (customer, driver, merchant staff, admin).

    Role-specific data lives in DriverProfile / RestaurantStaff rather than a
    single role column, since one person can hold more than one role — e.g. a
    driver who also places orders as a customer.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    driver_profile: Mapped[DriverProfile | None] = relationship(
        back_populates="user", uselist=False
    )
    restaurant_staff_memberships: Mapped[list[RestaurantStaff]] = relationship(
        back_populates="user"
    )
    addresses: Mapped[list[Address]] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(
        back_populates="customer", foreign_keys="Order.customer_id"
    )
