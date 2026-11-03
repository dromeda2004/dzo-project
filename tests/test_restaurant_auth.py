from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, require_restaurant_role
from app.core.database import get_db
from app.core.error_handlers import register_exception_handlers
from app.core.security import hash_password
from app.models import Restaurant, RestaurantStaff, User
from app.models.enums import RestaurantStaffRole

# No real route uses require_restaurant_role yet (menu and order endpoints come in
# later epic3 tasks), so these tests mount it on a throwaway app, one route per
# minimum role, rather than adding a placeholder route to the real app.
_app = FastAPI()
register_exception_handlers(_app)


def _add_route(min_role: RestaurantStaffRole) -> None:
    @_app.get(f"/restaurants/{{restaurant_id}}/{min_role.value}")
    async def route(
        restaurant: Restaurant = Depends(require_restaurant_role(min_role)),
    ) -> dict[str, int]:
        return {"restaurant_id": restaurant.id}


for _role in RestaurantStaffRole:
    _add_route(_role)


@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    _app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac
    _app.dependency_overrides.clear()


async def _create_user(db_session: AsyncSession, *, email: str, is_admin: bool = False) -> User:
    user = User(
        email=email,
        password_hash=hash_password("correct horse"),
        full_name="Test User",
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_restaurant(db_session: AsyncSession, name: str) -> Restaurant:
    restaurant = Restaurant(name=name, address="1 Test St")
    db_session.add(restaurant)
    await db_session.flush()
    return restaurant


async def _add_staff(
    db_session: AsyncSession, user: User, restaurant: Restaurant, role: RestaurantStaffRole
) -> None:
    db_session.add(RestaurantStaff(user=user, restaurant=restaurant, role=role))
    await db_session.flush()


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


RANK = {RestaurantStaffRole.STAFF: 0, RestaurantStaffRole.MANAGER: 1, RestaurantStaffRole.OWNER: 2}


@pytest.mark.parametrize("member_role", list(RestaurantStaffRole))
@pytest.mark.parametrize("min_role", list(RestaurantStaffRole))
async def test_role_hierarchy(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    member_role: RestaurantStaffRole,
    min_role: RestaurantStaffRole,
) -> None:
    user = await _create_user(db_session, email="member@example.com")
    restaurant = await _create_restaurant(db_session, "Mine")
    await _add_staff(db_session, user, restaurant, member_role)

    response = await auth_client.get(
        f"/restaurants/{restaurant.id}/{min_role.value}", headers=_auth(user)
    )

    expected = 200 if RANK[member_role] >= RANK[min_role] else 403
    assert response.status_code == expected


async def test_staff_of_another_restaurant_rejected(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner_of_a = await _create_user(db_session, email="owner-a@example.com")
    restaurant_a = await _create_restaurant(db_session, "A")
    restaurant_b = await _create_restaurant(db_session, "B")
    await _add_staff(db_session, owner_of_a, restaurant_a, RestaurantStaffRole.OWNER)

    response = await auth_client.get(
        f"/restaurants/{restaurant_b.id}/staff", headers=_auth(owner_of_a)
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Not on this restaurant's staff"


async def test_non_staff_user_rejected(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    customer = await _create_user(db_session, email="customer@example.com")
    restaurant = await _create_restaurant(db_session, "Mine")

    response = await auth_client.get(f"/restaurants/{restaurant.id}/staff", headers=_auth(customer))

    assert response.status_code == 403


async def test_admin_allowed_at_any_restaurant(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _create_user(db_session, email="admin@example.com", is_admin=True)
    restaurant = await _create_restaurant(db_session, "Not theirs")

    response = await auth_client.get(f"/restaurants/{restaurant.id}/owner", headers=_auth(admin))

    assert response.status_code == 200
    assert response.json() == {"restaurant_id": restaurant.id}


async def test_unknown_restaurant_returns_404(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _create_user(db_session, email="admin@example.com", is_admin=True)

    response = await auth_client.get("/restaurants/999999/staff", headers=_auth(admin))

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Restaurant not found"


async def test_unauthenticated_rejected(auth_client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant = await _create_restaurant(db_session, "Mine")

    response = await auth_client.get(f"/restaurants/{restaurant.id}/staff")

    assert response.status_code == 401
