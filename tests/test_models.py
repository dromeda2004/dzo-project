from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Address, DriverProfile, Order, Restaurant, RestaurantStaff, User
from app.models.enums import OrderStatus, RestaurantStaffRole


async def test_user_unique_email_constraint(db_session: AsyncSession) -> None:
    db_session.add(User(email="dupe@example.com", password_hash="x", full_name="A"))
    await db_session.flush()

    db_session.add(User(email="dupe@example.com", password_hash="x", full_name="B"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_order_defaults_to_placed_status(db_session: AsyncSession) -> None:
    user = User(email="customer@example.com", password_hash="x", full_name="Customer")
    restaurant = Restaurant(name="Test Kitchen", address="123 Main St")
    db_session.add_all([user, restaurant])
    await db_session.flush()

    address = Address(
        user_id=user.id, line1="123 Main St", city="Springfield", state="CA", postal_code="90000"
    )
    db_session.add(address)
    await db_session.flush()

    order = Order(
        customer_id=user.id,
        restaurant_id=restaurant.id,
        delivery_address_id=address.id,
        subtotal=Decimal("25.00"),
    )
    db_session.add(order)
    await db_session.flush()

    assert order.id is not None
    assert order.status == OrderStatus.PLACED
    assert order.tip == Decimal("0")


async def test_driver_profile_one_to_one_with_user(db_session: AsyncSession) -> None:
    user = User(email="driver@example.com", password_hash="x", full_name="Driver")
    db_session.add(user)
    await db_session.flush()

    db_session.add(DriverProfile(user_id=user.id))
    await db_session.flush()

    db_session.add(DriverProfile(user_id=user.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_restaurant_staff_unique_per_user_restaurant(db_session: AsyncSession) -> None:
    user = User(email="staff@example.com", password_hash="x", full_name="Staff")
    restaurant = Restaurant(name="Test Kitchen 2", address="456 Main St")
    db_session.add_all([user, restaurant])
    await db_session.flush()

    db_session.add(
        RestaurantStaff(
            user_id=user.id, restaurant_id=restaurant.id, role=RestaurantStaffRole.MANAGER
        )
    )
    await db_session.flush()

    db_session.add(
        RestaurantStaff(
            user_id=user.id, restaurant_id=restaurant.id, role=RestaurantStaffRole.STAFF
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
