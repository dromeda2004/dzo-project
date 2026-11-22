"""Acknowledge and cancel (epic3.task7), and the shared kitchen-tablet login."""

from datetime import UTC, datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Order, Restaurant
from app.models.enums import OrderStatus, RestaurantStaffRole
from app.services.order_lifecycle import transition
from tests.factories import (
    add_staff,
    auth,
    create_driver,
    create_order,
    create_restaurant,
    create_user,
    staffed_restaurant,
)

S = OrderStatus
settings = get_settings()


def url(restaurant: Restaurant, order: Order, action: str) -> str:
    return f"/restaurants/{restaurant.id}/orders/{order.id}/{action}"


async def current_status(db: AsyncSession, order: Order) -> S:
    await db.refresh(order)
    return order.status


# --- Acknowledge ---------------------------------------------------------------------


async def test_acknowledge_opens_the_order_for_claim(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)
    before = datetime.now(UTC)

    response = await client.post(
        url(restaurant, order, "acknowledge"),
        json={"prep_time_estimate_minutes": 20},
        headers=auth(staff),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == order.id
    assert body["status"] == "open_for_claim"
    assert body["prep_time_estimate_minutes"] == 20
    assert datetime.fromisoformat(body["acknowledged_at"]) >= before
    assert await current_status(db_session, order) == S.OPEN_FOR_CLAIM


async def test_acknowledging_twice_is_a_409(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)
    body = {"prep_time_estimate_minutes": 20}

    first = await client.post(url(restaurant, order, "acknowledge"), json=body, headers=auth(staff))
    second = await client.post(
        url(restaurant, order, "acknowledge"), json=body, headers=auth(staff)
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"
    assert "open_for_claim to acknowledged" in second.json()["error"]["message"]


@pytest.mark.parametrize("start", [S.CLAIMED, S.DELIVERED])
async def test_only_placed_orders_can_be_acknowledged(
    client: AsyncClient, db_session: AsyncSession, start: S
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant, status=start)

    response = await client.post(
        url(restaurant, order, "acknowledge"),
        json={"prep_time_estimate_minutes": 20},
        headers=auth(staff),
    )

    assert response.status_code == 409
    assert await current_status(db_session, order) == start


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"prep_time_estimate_minutes": 0},
        {"prep_time_estimate_minutes": 181},
        {"prep_time_estimate_minutes": "soon"},
    ],
)
async def test_acknowledge_needs_a_sane_prep_time(
    client: AsyncClient, db_session: AsyncSession, body: dict
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)

    response = await client.post(
        url(restaurant, order, "acknowledge"), json=body, headers=auth(staff)
    )

    assert response.status_code == 422
    assert await current_status(db_session, order) == S.PLACED


async def test_acknowledge_accepts_the_bounds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    for minutes in (1, 180):
        order = await create_order(db_session, restaurant, customer_email=f"c{minutes}@example.com")
        response = await client.post(
            url(restaurant, order, "acknowledge"),
            json={"prep_time_estimate_minutes": minutes},
            headers=auth(staff),
        )
        assert response.status_code == 200


# --- Cancel --------------------------------------------------------------------------


@pytest.mark.parametrize("start", [S.PLACED, S.ACKNOWLEDGED, S.OPEN_FOR_CLAIM])
async def test_cancel_before_a_driver_claims(
    client: AsyncClient, db_session: AsyncSession, start: S
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant, status=start)

    response = await client.post(
        url(restaurant, order, "cancel"),
        json={"reason": "item_unavailable", "note": "  Out of fish  "},
        headers=auth(staff),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert (body["cancellation_reason"], body["cancellation_note"]) == (
        "item_unavailable",
        "Out of fish",
    )
    assert body["cancelled_at"] is not None
    assert await current_status(db_session, order) == S.CANCELLED


@pytest.mark.parametrize("start", [S.CLAIMED, S.READY_TIME_SET, S.PICKED_UP, S.DELIVERED])
async def test_cancel_after_a_driver_claims_is_a_409(
    client: AsyncClient, db_session: AsyncSession, start: S
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant, status=start)

    response = await client.post(
        url(restaurant, order, "cancel"), json={"reason": "too_busy"}, headers=auth(staff)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert await current_status(db_session, order) == start


async def test_a_cancelled_order_stays_cancelled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)
    cancel = {"reason": "closing"}

    assert (
        await client.post(url(restaurant, order, "cancel"), json=cancel, headers=auth(staff))
    ).status_code == 200
    again = await client.post(url(restaurant, order, "cancel"), json=cancel, headers=auth(staff))
    acknowledge = await client.post(
        url(restaurant, order, "acknowledge"),
        json={"prep_time_estimate_minutes": 10},
        headers=auth(staff),
    )

    assert (again.status_code, acknowledge.status_code) == (409, 409)
    # Gone from the default inbox, still there when asked for.
    inbox = await client.get(f"/restaurants/{restaurant.id}/orders", headers=auth(staff))
    assert inbox.json()["orders"] == []
    cancelled = await client.get(
        f"/restaurants/{restaurant.id}/orders", params={"status": "cancelled"}, headers=auth(staff)
    )
    assert [o["id"] for o in cancelled.json()["orders"]] == [order.id]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": "bored"},
        {"reason": "other"},
        {"reason": "other", "note": "   "},
        {"reason": "too_busy", "note": "x" * 501},
    ],
)
async def test_cancel_needs_a_valid_reason(
    client: AsyncClient, db_session: AsyncSession, body: dict
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)

    response = await client.post(url(restaurant, order, "cancel"), json=body, headers=auth(staff))

    assert response.status_code == 422
    assert await current_status(db_session, order) == S.PLACED


async def test_other_with_a_note_is_accepted(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)

    response = await client.post(
        url(restaurant, order, "cancel"),
        json={"reason": "other", "note": "Power cut"},
        headers=auth(staff),
    )

    assert response.status_code == 200
    assert response.json()["cancellation_note"] == "Power cut"


# --- Who can act ---------------------------------------------------------------------


@pytest.mark.parametrize("role", list(RestaurantStaffRole))
@pytest.mark.parametrize("action", ["acknowledge", "cancel"])
async def test_every_staff_role_can_act(
    client: AsyncClient, db_session: AsyncSession, role: RestaurantStaffRole, action: str
) -> None:
    restaurant, member = await staffed_restaurant(db_session, role)
    order = await create_order(db_session, restaurant)
    body = {"prep_time_estimate_minutes": 15} if action == "acknowledge" else {"reason": "too_busy"}

    response = await client.post(url(restaurant, order, action), json=body, headers=auth(member))

    assert response.status_code == 200


@pytest.mark.parametrize("action", ["acknowledge", "cancel"])
async def test_outsiders_cannot_act(
    client: AsyncClient, db_session: AsyncSession, action: str
) -> None:
    mine, staff = await staffed_restaurant(db_session, RestaurantStaffRole.OWNER, name="Mine")
    theirs = await create_restaurant(db_session, "Theirs")
    their_order = await create_order(db_session, theirs, customer_email="theirs@example.com")
    body = {"prep_time_estimate_minutes": 15} if action == "acknowledge" else {"reason": "too_busy"}

    # Their restaurant: not on its staff. Their order through my path: not found.
    assert (
        await client.post(url(theirs, their_order, action), json=body, headers=auth(staff))
    ).status_code == 403
    assert (
        await client.post(url(mine, their_order, action), json=body, headers=auth(staff))
    ).status_code == 404
    # The customer who placed it can't act as the restaurant, and nobody anonymous can.
    customer = await create_user(db_session, email="nosy@example.com")
    assert (
        await client.post(url(theirs, their_order, action), json=body, headers=auth(customer))
    ).status_code == 403
    assert (await client.post(url(theirs, their_order, action), json=body)).status_code == 401

    assert await current_status(db_session, their_order) == S.PLACED


# --- Shared kitchen tablet -----------------------------------------------------------


async def _login(client: AsyncClient, email: str, **extra: object) -> dict:
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct horse", **extra}
    )
    assert response.status_code == 200
    return response.json()


def _lifetime(token: str) -> timedelta:
    claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    return datetime.fromtimestamp(claims["exp"], UTC) - datetime.now(UTC)


async def test_stay_signed_in_gives_a_30_day_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="kitchen@example.com")

    normal = await _login(client, "kitchen@example.com")
    tablet = await _login(client, "kitchen@example.com", stay_signed_in=True)

    assert normal["expires_in"] == 24 * 60 * 60
    assert tablet["expires_in"] == 30 * 24 * 60 * 60
    assert timedelta(hours=23) < _lifetime(normal["access_token"]) <= timedelta(hours=24)
    assert timedelta(days=29) < _lifetime(tablet["access_token"]) <= timedelta(days=30)


async def test_removing_the_tablet_from_staff_cuts_access_immediately(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session, RestaurantStaffRole.OWNER)
    kitchen = await create_user(db_session, email="kitchen@example.com")
    kitchen.password_hash = hash_password("correct horse")
    await add_staff(db_session, kitchen, restaurant, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant)
    token = (await _login(client, "kitchen@example.com", stay_signed_in=True))["access_token"]
    tablet = {"Authorization": f"Bearer {token}"}
    inbox = f"/restaurants/{restaurant.id}/orders"
    acknowledge = url(restaurant, order, "acknowledge")

    assert (await client.get(inbox, headers=tablet)).status_code == 200

    removed = await client.delete(
        f"/restaurants/{restaurant.id}/staff/{kitchen.id}", headers=auth(owner)
    )
    assert removed.status_code == 204

    # Same unexpired 30-day token, refused on the very next request.
    db_session.expire_all()
    assert (await client.get(inbox, headers=tablet)).status_code == 403
    response = await client.post(
        acknowledge,
        json={"prep_time_estimate_minutes": 10},
        headers=tablet,
    )
    assert response.status_code == 403


# --- Ready-time signal (epic3.task8) ----------------------------------------------


async def claimed_order(db: AsyncSession, restaurant: Restaurant) -> Order:
    order = await create_order(db, restaurant, status=S.OPEN_FOR_CLAIM)
    driver = await create_driver(db)
    await transition(db, order, S.CLAIMED, driver_id=driver.id)
    return order


def _at(body: dict) -> datetime:
    return datetime.fromisoformat(body["ready_time"])


@pytest.mark.parametrize("minutes", [0, 10, 180])
async def test_ready_in_minutes(
    client: AsyncClient, db_session: AsyncSession, minutes: int
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await claimed_order(db_session, restaurant)
    before = datetime.now(UTC)

    response = await client.post(
        url(restaurant, order, "ready-time"),
        json={"ready_in_minutes": minutes},
        headers=auth(staff),
    )

    after = datetime.now(UTC)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready_time_set"
    assert body["driver"] is not None
    expected = timedelta(minutes=minutes)
    assert before + expected <= _at(body) <= after + expected
    assert await current_status(db_session, order) == S.READY_TIME_SET


async def test_ready_at_a_specific_time(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await claimed_order(db_session, restaurant)
    # Given in the restaurant's own offset; stored and returned as the same instant.
    ready = (datetime.now(UTC) + timedelta(minutes=25)).replace(microsecond=0)
    local = ready.astimezone(timezone(timedelta(hours=-8)))

    response = await client.post(
        url(restaurant, order, "ready-time"),
        json={"ready_at": local.isoformat()},
        headers=auth(staff),
    )

    assert response.status_code == 200
    assert _at(response.json()) == ready


async def test_ready_at_within_clock_skew_is_stored_as_now(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await claimed_order(db_session, restaurant)
    before = datetime.now(UTC)
    slightly_behind = before - timedelta(seconds=30)

    response = await client.post(
        url(restaurant, order, "ready-time"),
        json={"ready_at": slightly_behind.isoformat()},
        headers=auth(staff),
    )

    assert response.status_code == 200
    assert _at(response.json()) >= before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"ready_in_minutes": 10, "ready_at": "2030-01-01T00:00:00Z"},
        {"ready_in_minutes": -1},
        {"ready_in_minutes": 181},
        {"ready_at": "2020-01-01T00:00:00Z"},  # past
        {"ready_at": "PAST_5_MIN"},  # past, beyond the clock-skew allowance
        {"ready_at": "FUTURE_4_HOURS"},  # too far ahead
        {"ready_at": "2030-01-01T18:00:00"},  # no timezone
        {"ready_at": "soon"},
    ],
)
async def test_ready_time_rejects_bad_times(
    client: AsyncClient, db_session: AsyncSession, body: dict
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await claimed_order(db_session, restaurant)
    now = datetime.now(UTC)
    relative = {
        "PAST_5_MIN": now - timedelta(minutes=5),
        "FUTURE_4_HOURS": now + timedelta(hours=4),
    }
    if body.get("ready_at") in relative:
        body = {"ready_at": relative[body["ready_at"]].isoformat()}

    response = await client.post(
        url(restaurant, order, "ready-time"), json=body, headers=auth(staff)
    )

    assert response.status_code == 422
    assert await current_status(db_session, order) == S.CLAIMED


@pytest.mark.parametrize(
    "start", [S.PLACED, S.ACKNOWLEDGED, S.OPEN_FOR_CLAIM, S.READY_TIME_SET, S.DELIVERED]
)
async def test_ready_time_only_on_a_claimed_order(
    client: AsyncClient, db_session: AsyncSession, start: S
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant, status=start)

    response = await client.post(
        url(restaurant, order, "ready-time"), json={"ready_in_minutes": 5}, headers=auth(staff)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert await current_status(db_session, order) == start


async def test_ready_time_cannot_be_set_twice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await claimed_order(db_session, restaurant)
    ready = url(restaurant, order, "ready-time")

    first = await client.post(ready, json={"ready_in_minutes": 10}, headers=auth(staff))
    second = await client.post(ready, json={"ready_in_minutes": 0}, headers=auth(staff))

    assert (first.status_code, second.status_code) == (200, 409)


@pytest.mark.parametrize("role", list(RestaurantStaffRole))
async def test_every_staff_role_can_set_the_ready_time(
    client: AsyncClient, db_session: AsyncSession, role: RestaurantStaffRole
) -> None:
    restaurant, member = await staffed_restaurant(db_session, role)
    order = await claimed_order(db_session, restaurant)

    response = await client.post(
        url(restaurant, order, "ready-time"), json={"ready_in_minutes": 5}, headers=auth(member)
    )

    assert response.status_code == 200


async def test_outsiders_cannot_set_the_ready_time(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, staff = await staffed_restaurant(db_session, RestaurantStaffRole.OWNER, name="Mine")
    theirs = await create_restaurant(db_session, "Theirs")
    their_order = await claimed_order(db_session, theirs)
    body = {"ready_in_minutes": 5}

    assert (
        await client.post(url(theirs, their_order, "ready-time"), json=body, headers=auth(staff))
    ).status_code == 403
    assert (
        await client.post(url(mine, their_order, "ready-time"), json=body, headers=auth(staff))
    ).status_code == 404
    assert (await client.post(url(theirs, their_order, "ready-time"), json=body)).status_code == 401
    assert await current_status(db_session, their_order) == S.CLAIMED
