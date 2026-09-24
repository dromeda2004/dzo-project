"""Walks a sample order through all seven lifecycle states in docs/AGENTS_DZO.md
section 1, printing the status at each step. Rolls back at the end — no demo
data is left in the database. Requires `make db-up` and `make migrate` first.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.models import Address, Order, Restaurant, User
from app.models.enums import OrderStatus


async def main() -> None:
    async with AsyncSessionLocal() as session:
        customer = User(
            email="demo-customer@example.com", password_hash="x", full_name="Demo Customer"
        )
        restaurant = Restaurant(name="Demo Kitchen", address="1 Demo St")
        session.add_all([customer, restaurant])
        await session.flush()

        address = Address(
            user_id=customer.id,
            line1="1 Demo St",
            city="Springfield",
            state="CA",
            postal_code="90000",
        )
        session.add(address)
        await session.flush()

        order = Order(
            customer_id=customer.id,
            restaurant_id=restaurant.id,
            delivery_address_id=address.id,
            subtotal=Decimal("18.50"),
        )
        session.add(order)
        await session.flush()
        print(f"1. Order placed        -> status={order.status.value}")

        order.status = OrderStatus.ACKNOWLEDGED
        order.prep_time_estimate_minutes = 20
        order.acknowledged_at = datetime.now(UTC)
        print(f"2. Restaurant acks     -> status={order.status.value}, prep=20min")

        order.status = OrderStatus.OPEN_FOR_CLAIM
        print(f"3. Open for claim      -> status={order.status.value}")

        order.status = OrderStatus.CLAIMED
        order.claimed_at = datetime.now(UTC)
        print(f"4. Driver claims       -> status={order.status.value}")

        order.status = OrderStatus.READY_TIME_SET
        order.ready_time = datetime.now(UTC)
        print(f"5. Ready-time set      -> status={order.status.value}")

        order.status = OrderStatus.PICKED_UP
        order.picked_up_at = datetime.now(UTC)
        print(f"6. Picked up           -> status={order.status.value}")

        order.status = OrderStatus.DELIVERED
        order.delivered_at = datetime.now(UTC)
        print(f"7. Delivered           -> status={order.status.value}")

        await session.rollback()
        print("\nRolled back — demo data not persisted.")


if __name__ == "__main__":
    asyncio.run(main())
