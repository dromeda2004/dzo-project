import enum


class RestaurantStaffRole(enum.StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class OrderStatus(enum.StrEnum):
    """The seven-state order lifecycle — see docs/AGENTS_DZO.md section 1."""

    PLACED = "placed"
    ACKNOWLEDGED = "acknowledged"
    OPEN_FOR_CLAIM = "open_for_claim"
    CLAIMED = "claimed"
    READY_TIME_SET = "ready_time_set"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"


class RaterRole(enum.StrEnum):
    CUSTOMER = "customer"
    RESTAURANT = "restaurant"
    DRIVER = "driver"


class RateeType(enum.StrEnum):
    """What Rating.ratee_id points to — a users row (driver/customer) or a restaurants row."""

    USER = "user"
    RESTAURANT = "restaurant"


class DriverSubscriptionStatus(enum.StrEnum):
    TRIAL = "trial"
    SUBSCRIBED = "subscribed"
    DECLINED = "declined"
    CANCELED = "canceled"


class PromotionDiscountType(enum.StrEnum):
    PERCENTAGE = "percentage"
    FLAT = "flat"


class PaymentStatus(enum.StrEnum):
    PENDING = "pending"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"


class PayoutRecipientType(enum.StrEnum):
    """What Payout.recipient_id points to — a restaurants row or a driver_profiles row."""

    RESTAURANT = "restaurant"
    DRIVER = "driver"


class PayoutStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
