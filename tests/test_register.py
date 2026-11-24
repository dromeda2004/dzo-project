"""Customer self-registration (epic4.task1)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import RestaurantStaff, User
from tests.factories import create_restaurant, create_user

PASSWORD = "correct horse"


def _body(**overrides: str) -> dict[str, str]:
    return {"email": "new@example.com", "password": PASSWORD, "full_name": "Ana Cruz", **overrides}


async def test_register_creates_customer_and_signs_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/auth/register", json=_body(email="Ana@Example.com"))

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 24 * 60 * 60

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"
    assert me.json()["full_name"] == "Ana Cruz"
    assert me.json()["is_admin"] is False

    user = await db_session.scalar(select(User).where(User.email == "ana@example.com"))
    assert user is not None
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)


async def test_registered_customer_can_log_in(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_body())

    response = await client.post(
        "/auth/login", json={"email": "NEW@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_registered_customer_has_no_staff_rights(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant = await create_restaurant(db_session)
    token = (await client.post("/auth/register", json=_body())).json()["access_token"]

    response = await client.get(
        f"/restaurants/{restaurant.id}/orders", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    memberships = await db_session.scalars(
        select(RestaurantStaff).join(User).where(User.email == "new@example.com")
    )
    assert memberships.all() == []


async def test_duplicate_email_rejected_in_any_case(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="taken@example.com")

    response = await client.post("/auth/register", json=_body(email="Taken@Example.COM"))

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "An account with this email already exists"


async def test_weak_password_rejected(client: AsyncClient) -> None:
    response = await client.post("/auth/register", json=_body(password="short"))

    assert response.status_code == 422
    assert "password" in response.json()["error"]["fields"]


async def test_invalid_email_and_blank_name_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json=_body(email="not-an-email", full_name="   ")
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert "email" in fields and "full_name" in fields


async def test_cannot_register_as_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    # Unknown fields are ignored; nothing in the body can grant admin.
    body = {**_body(), "is_admin": True}
    response = await client.post("/auth/register", json=body)

    assert response.status_code == 201
    user = await db_session.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None and user.is_admin is False
