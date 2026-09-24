from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User


async def _create_user(
    db_session: AsyncSession, *, email: str, password: str, is_admin: bool = False
) -> User:
    user = User(
        email=email, password_hash=hash_password(password), full_name="Test User", is_admin=is_admin
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_login_success_returns_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="login@example.com", password="correct horse")

    response = await client.post(
        "/auth/login", json={"email": "login@example.com", "password": "correct horse"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="wrongpw@example.com", password="correct horse")

    response = await client.post(
        "/auth/login", json={"email": "wrongpw@example.com", "password": "nope"}
    )

    assert response.status_code == 401


async def test_login_unknown_email_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401


async def test_me_returns_current_user_with_valid_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, email="me@example.com", password="correct horse")
    login_response = await client.post(
        "/auth/login", json={"email": "me@example.com", "password": "correct horse"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_admin_ping_rejects_non_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session, email="regular@example.com", password="correct horse")
    login_response = await client.post(
        "/auth/login", json={"email": "regular@example.com", "password": "correct horse"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_admin_ping_allows_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(
        db_session, email="admin@example.com", password="correct horse", is_admin=True
    )
    login_response = await client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "correct horse"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
