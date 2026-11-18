"""Shared helpers for creating users, restaurants, staff, drivers, and orders in tests."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.security import hash_password
from app.models import Address, DriverProfile, Order, Restaurant, RestaurantStaff, User
from app.models.enums import OrderStatus, RestaurantStaffRole


async def create_user(db_session: AsyncSession, *, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        password_hash=hash_password("correct horse"),
        full_name="Test User",
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_restaurant(db_session: AsyncSession, name: str = "Pilot") -> Restaurant:
    restaurant = Restaurant(name=name, address="1 Test St")
    db_session.add(restaurant)
    await db_session.flush()
    return restaurant


async def add_staff(
    db_session: AsyncSession, user: User, restaurant: Restaurant, role: RestaurantStaffRole
) -> None:
    db_session.add(RestaurantStaff(user=user, restaurant=restaurant, role=role))
    await db_session.flush()


async def staffed_restaurant(
    db_session: AsyncSession,
    role: RestaurantStaffRole = RestaurantStaffRole.OWNER,
    *,
    name: str = "Pilot",
    email: str | None = None,
) -> tuple[Restaurant, User]:
    restaurant = await create_restaurant(db_session, name)
    member = await create_user(db_session, email=email or f"{role.value}@example.com")
    await add_staff(db_session, member, restaurant, role)
    return restaurant, member


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def create_driver(
    db_session: AsyncSession, *, email: str = "driver@example.com"
) -> DriverProfile:
    user = await create_user(db_session, email=email)
    profile = DriverProfile(user_id=user.id)
    db_session.add(profile)
    await db_session.flush()
    return profile


async def create_order(
    db_session: AsyncSession,
    restaurant: Restaurant | None = None,
    *,
    status: OrderStatus = OrderStatus.PLACED,
    customer_email: str = "customer@example.com",
) -> Order:
    """An order with no items, for tests that only care about its status. Inserting it
    straight into a later status skips the lifecycle guard, so use that only to set
    up a starting point."""
    restaurant = restaurant or await create_restaurant(db_session)
    customer = await create_user(db_session, email=customer_email)
    address = Address(
        user_id=customer.id, line1="1 Test St", city="Springfield", state="CA", postal_code="90000"
    )
    db_session.add(address)
    await db_session.flush()
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        delivery_address_id=address.id,
        subtotal=Decimal("10.00"),
        status=status,
    )
    db_session.add(order)
    await db_session.flush()
    return order
