from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import Restaurant, RestaurantStaff, User
from app.models.enums import RestaurantStaffRole
from tests.factories import add_staff, auth, create_restaurant, create_user, staffed_restaurant

# --- Restaurants -----------------------------------------------------------------


async def test_admin_creates_restaurant(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)

    response = await client.post(
        "/restaurants", json={"name": "Pilot", "address": "1 Main St"}, headers=auth(admin)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Pilot"
    assert body["timezone"] == "America/Los_Angeles"
    assert body["is_active"] is True
    assert await db_session.get(Restaurant, body["id"]) is not None


async def test_restaurant_name_cannot_be_nulled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)
    restaurant = await create_restaurant(db_session)

    response = await client.patch(
        f"/restaurants/{restaurant.id}", json={"name": None}, headers=auth(admin)
    )

    assert response.status_code == 422


async def test_non_admin_cannot_create_restaurant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, owner = await staffed_restaurant(db_session)

    response = await client.post(
        "/restaurants", json={"name": "Mine", "address": "1 Main St"}, headers=auth(owner)
    )

    assert response.status_code == 403


async def test_unknown_timezone_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)

    response = await client.post(
        "/restaurants",
        json={"name": "Pilot", "address": "1 Main St", "timezone": "Mars/Olympus"},
        headers=auth(admin),
    )

    assert response.status_code == 422
    assert "timezone" in response.json()["error"]["fields"]


async def test_admin_updates_and_deactivates_restaurant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)
    restaurant = await create_restaurant(db_session)

    response = await client.patch(
        f"/restaurants/{restaurant.id}",
        json={"name": "Renamed", "is_active": False},
        headers=auth(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["address"], body["is_active"]) == ("Renamed", "1 Test St", False)


async def test_owner_cannot_update_restaurant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.patch(
        f"/restaurants/{restaurant.id}", json={"is_active": False}, headers=auth(owner)
    )

    assert response.status_code == 403


async def test_staff_can_read_their_restaurant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    outsider = await create_user(db_session, email="outsider@example.com")

    own = await client.get(f"/restaurants/{restaurant.id}", headers=auth(staff))
    other = await client.get(f"/restaurants/{restaurant.id}", headers=auth(outsider))

    assert own.status_code == 200
    assert other.status_code == 403


# --- Adding staff ----------------------------------------------------------------


async def test_admin_onboards_new_owner_who_can_then_log_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)
    restaurant = await create_restaurant(db_session)

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={
            "email": "New.Owner@Example.com",
            "role": "owner",
            "full_name": "New Owner",
            "password": "temporary-pass",
        },
        headers=auth(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.owner@example.com"
    assert body["role"] == "owner"
    assert "password" not in response.text
    user = await db_session.get(User, body["user_id"])
    assert user is not None
    assert user.password_hash != "temporary-pass"
    assert verify_password("temporary-pass", user.password_hash)

    login = await client.post(
        "/auth/login", json={"email": "new.owner@example.com", "password": "temporary-pass"}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    staff = await client.get(
        f"/restaurants/{restaurant.id}/staff", headers={"Authorization": f"Bearer {token}"}
    )
    assert staff.status_code == 200


async def test_existing_account_is_attached_not_duplicated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    existing = await create_user(db_session, email="charlie@example.com")

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={"email": "Charlie@Example.com", "role": "manager"},
        headers=auth(owner),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == existing.id
    count = await db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(func.lower(User.email) == "charlie@example.com")
    )
    assert count == 1


async def test_existing_account_with_password_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    await create_user(db_session, email="charlie@example.com")

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={
            "email": "charlie@example.com",
            "role": "staff",
            "full_name": "Charlie",
            "password": "overwrite-attempt",
        },
        headers=auth(owner),
    )

    assert response.status_code == 409


async def test_new_account_requires_name_and_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={"email": "nobody@example.com", "role": "staff"},
        headers=auth(owner),
    )

    assert response.status_code == 422


async def test_short_temporary_password_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={"email": "new@example.com", "role": "staff", "full_name": "New", "password": "short"},
        headers=auth(owner),
    )

    assert response.status_code == 422
    assert "password" in response.json()["error"]["fields"]


async def test_adding_existing_staff_member_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={"email": owner.email, "role": "staff"},
        headers=auth(owner),
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Already on this restaurant's staff"


async def test_manager_cannot_add_staff(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, manager = await staffed_restaurant(db_session, RestaurantStaffRole.MANAGER)
    await create_user(db_session, email="someone@example.com")

    response = await client.post(
        f"/restaurants/{restaurant.id}/staff",
        json={"email": "someone@example.com", "role": "staff"},
        headers=auth(manager),
    )

    assert response.status_code == 403


# --- Listing, changing, and removing staff ---------------------------------------


async def test_staff_list_is_owner_only_and_hides_password_hashes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    staff = await create_user(db_session, email="line-cook@example.com")
    await add_staff(db_session, staff, restaurant, RestaurantStaffRole.STAFF)

    as_owner = await client.get(f"/restaurants/{restaurant.id}/staff", headers=auth(owner))
    as_staff = await client.get(f"/restaurants/{restaurant.id}/staff", headers=auth(staff))

    assert as_owner.status_code == 200
    assert [m["email"] for m in as_owner.json()] == ["owner@example.com", "line-cook@example.com"]
    assert all(set(m) == {"user_id", "email", "full_name", "role"} for m in as_owner.json())
    # Staff can't see colleagues' contact details.
    assert as_staff.status_code == 403


async def test_owner_changes_staff_role(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    staff = await create_user(db_session, email="line-cook@example.com")
    await add_staff(db_session, staff, restaurant, RestaurantStaffRole.STAFF)

    response = await client.patch(
        f"/restaurants/{restaurant.id}/staff/{staff.id}",
        json={"role": "manager"},
        headers=auth(owner),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "manager"


async def test_last_owner_cannot_be_demoted(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.patch(
        f"/restaurants/{restaurant.id}/staff/{owner.id}",
        json={"role": "manager"},
        headers=auth(owner),
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "A restaurant must keep at least one owner"


async def test_owner_can_be_demoted_when_another_owner_exists(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    co_owner = await create_user(db_session, email="co-owner@example.com")
    await add_staff(db_session, co_owner, restaurant, RestaurantStaffRole.OWNER)

    response = await client.patch(
        f"/restaurants/{restaurant.id}/staff/{co_owner.id}",
        json={"role": "manager"},
        headers=auth(owner),
    )

    assert response.status_code == 200


async def test_last_owner_cannot_be_removed(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.delete(
        f"/restaurants/{restaurant.id}/staff/{owner.id}", headers=auth(owner)
    )

    assert response.status_code == 409


async def test_removing_staff_keeps_their_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    staff = await create_user(db_session, email="line-cook@example.com")
    await add_staff(db_session, staff, restaurant, RestaurantStaffRole.STAFF)

    response = await client.delete(
        f"/restaurants/{restaurant.id}/staff/{staff.id}", headers=auth(owner)
    )

    assert response.status_code == 204
    membership = await db_session.scalar(
        select(RestaurantStaff).where(RestaurantStaff.user_id == staff.id)
    )
    assert membership is None
    assert await db_session.get(User, staff.id) is not None
    # And they immediately lose access, since roles are read per request.
    after = await client.get(f"/restaurants/{restaurant.id}", headers=auth(staff))
    assert after.status_code == 403


async def test_removing_unknown_staff_member_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.delete(
        f"/restaurants/{restaurant.id}/staff/999999", headers=auth(owner)
    )

    assert response.status_code == 404
