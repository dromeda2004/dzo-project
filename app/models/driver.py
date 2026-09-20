from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import DriverSubscriptionStatus

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class DriverProfile(Base, TimestampMixin):
    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    vehicle_description: Mapped[str | None] = mapped_column(String(255))
    background_check_status: Mapped[str] = mapped_column(
        String(50), default="pending", server_default="pending"
    )
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    user: Mapped[User] = relationship(back_populates="driver_profile")
    subscription: Mapped[DriverSubscription | None] = relationship(
        back_populates="driver_profile", uselist=False
    )
    location: Mapped[DriverLocation | None] = relationship(
        back_populates="driver_profile", uselist=False
    )
    orders: Mapped[list[Order]] = relationship(back_populates="driver")


class DriverLocation(Base, TimestampMixin):
    """Last-known location per driver — not a ping-history table.

    A separate location-history table is a reasonable addition once live
    tracking (DZO Ride's dispatch map) needs a trail rather than just "where
    is this driver right now."
    """

    __tablename__ = "driver_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_profile_id: Mapped[int] = mapped_column(
        ForeignKey("driver_profiles.id"), unique=True, index=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    driver_profile: Mapped[DriverProfile] = relationship(back_populates="location")


class DriverSubscription(Base, TimestampMixin):
    """Tracks the $99/month driver subscription and 30-day trial — roadmap section 8."""

    __tablename__ = "driver_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_profile_id: Mapped[int] = mapped_column(
        ForeignKey("driver_profiles.id"), unique=True, index=True
    )
    status: Mapped[DriverSubscriptionStatus] = mapped_column(
        Enum(DriverSubscriptionStatus, name="driver_subscription_status"),
        default=DriverSubscriptionStatus.TRIAL,
    )
    trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    driver_profile: Mapped[DriverProfile] = relationship(back_populates="subscription")
