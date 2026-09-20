from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import RateeType, RaterRole

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Rating(Base, TimestampMixin):
    """Covers all three rating directions — customer<->restaurant, customer<->driver,
    restaurant<->driver — in one table rather than three separate ones.

    ratee_id is polymorphic (a users.id or a restaurants.id, per ratee_type) so
    it isn't a real foreign key.
    """

    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    rater_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rater_role: Mapped[RaterRole] = mapped_column(Enum(RaterRole, name="rater_role"))
    ratee_type: Mapped[RateeType] = mapped_column(Enum(RateeType, name="ratee_type"))
    ratee_id: Mapped[int] = mapped_column(index=True)
    score: Mapped[int]
    comment: Mapped[str | None] = mapped_column(String(1000))

    order: Mapped[Order] = relationship(back_populates="ratings")
    rater: Mapped[User] = relationship(foreign_keys=[rater_user_id])
