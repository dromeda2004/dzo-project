"""Shared helpers for creating users, restaurants, and staff in tests."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.security import hash_password
from app.models import Restaurant, RestaurantStaff, User
from app.models.enums import RestaurantStaffRole


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
