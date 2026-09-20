from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import PaymentStatus, PayoutRecipientType, PayoutStatus

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(Base, TimestampMixin):
    """One row per order — references the payment processor's intent only.

    No raw card data touches these servers (docs/AGENTS_DZO.md section 3);
    capture goes through the processor's SDK (Stripe Connect per the roadmap).
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    processor_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.PENDING
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    platform_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    restaurant_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    driver_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="payment")


class Payout(Base, TimestampMixin):
    """A payout batch to a restaurant or a driver.

    recipient_id is polymorphic (a restaurants.id or a driver_profiles.id
    depending on recipient_type) so it isn't a real foreign key — a deliberate
    simplification until payouts need their own dedicated query patterns.
    """

    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_type: Mapped[PayoutRecipientType] = mapped_column(
        Enum(PayoutRecipientType, name="payout_recipient_type")
    )
    recipient_id: Mapped[int] = mapped_column(index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payout_status"), default=PayoutStatus.PENDING
    )
    processor_payout_id: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
