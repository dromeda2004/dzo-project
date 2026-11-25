"""Saved delivery addresses (epic4.task2)."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Address, Order, User
from app.routers.addresses import MAX_ADDRESSES
from tests.factories import auth, create_restaurant, create_user

HOME = {
    "line1": " 12 Main St ",
    "line2": "Apt 4",
    "city": "Springfield",
    "state": "CA",
    "postal_code": "90001",
    "delivery_instructions": "Ring twice",
}


async def _customer(db: AsyncSession, email: str = "cust@example.com") -> User:
    return await create_user(db, email=email)


async def _add(client: AsyncClient, user: User, **overrides: str | None) -> dict:
    response = await client.post("/me/addresses", json={**HOME, **overrides}, headers=auth(user))
    assert response.status_code == 201, response.text
    return response.json()


async def _order_to(db: AsyncSession, user: User, address_id: int) -> Order:
    restaurant = await create_restaurant(db)
    order = Order(
        customer_id=user.id,
        restaurant_id=restaurant.id,
        delivery_address_id=address_id,
        subtotal=Decimal("10.00"),
    )
    db.add(order)
    await db.flush()
    return order


async def test_add_list_get_update_delete(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await _customer(db_session)
    created = await _add(client, user)
    assert created["line1"] == "12 Main St"  # trimmed
    assert created["delivery_instructions"] == "Ring twice"

    listed = await client.get("/me/addresses", headers=auth(user))
    assert [a["id"] for a in listed.json()] == [created["id"]]

    url = f"/me/addresses/{created['id']}"
    assert (await client.get(url, headers=auth(user))).json() == created

    updated = await client.patch(
        url, json={"line2": None, "delivery_instructions": "Leave at door"}, headers=auth(user)
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == created["id"]  # unused, so edited in place
    assert updated.json()["line2"] is None
    assert updated.json()["delivery_instructions"] == "Leave at door"

    assert (await client.delete(url, headers=auth(user))).status_code == 204
    assert (await client.get(url, headers=auth(user))).status_code == 404
    # Never used by an order, so it's really gone.
    assert await db_session.get(Address, created["id"]) is None


async def test_list_is_oldest_first_and_only_mine(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    me = await _customer(db_session)
    other = await _customer(db_session, "other@example.com")
    first = await _add(client, me, line1="1 First St")
    await _add(client, other)
    second = await _add(client, me, line1="2 Second St")

    listed = (await client.get("/me/addresses", headers=auth(me))).json()
    assert [a["id"] for a in listed] == [first["id"], second["id"]]


async def test_other_customers_address_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _customer(db_session)
    intruder = await _customer(db_session, "intruder@example.com")
    address = await _add(client, owner)
    url = f"/me/addresses/{address['id']}"

    assert (await client.get(url, headers=auth(intruder))).status_code == 404
    patched = await client.patch(url, json={"line1": "Mine now"}, headers=auth(intruder))
    assert patched.status_code == 404
    assert (await client.delete(url, headers=auth(intruder))).status_code == 404
    assert (await client.get(url, headers=auth(owner))).json()["line1"] == "12 Main St"


async def test_deleting_a_used_address_archives_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _customer(db_session)
    address = await _add(client, user)
    order = await _order_to(db_session, user, address["id"])

    url = f"/me/addresses/{address['id']}"
    assert (await client.delete(url, headers=auth(user))).status_code == 204
    assert (await client.get(url, headers=auth(user))).status_code == 404
    assert (await client.get("/me/addresses", headers=auth(user))).json() == []

    # The order still points at the original, unchanged address.
    stored = await db_session.get(Address, address["id"])
    assert stored is not None and stored.is_archived and stored.line1 == "12 Main St"
    assert order.delivery_address_id == address["id"]


async def test_editing_a_used_address_keeps_the_orders_copy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _customer(db_session)
    address = await _add(client, user)
    await _order_to(db_session, user, address["id"])

    response = await client.patch(
        f"/me/addresses/{address['id']}", json={"line1": "99 New Rd"}, headers=auth(user)
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["id"] != address["id"]
    assert edited["line1"] == "99 New Rd"
    assert edited["city"] == "Springfield" and edited["line2"] == "Apt 4"

    old = await db_session.get(Address, address["id"])
    assert old is not None and old.is_archived and old.line1 == "12 Main St"
    listed = (await client.get("/me/addresses", headers=auth(user))).json()
    assert [a["id"] for a in listed] == [edited["id"]]
    old_url = f"/me/addresses/{address['id']}"
    assert (await client.get(old_url, headers=auth(user))).status_code == 404


async def test_location_edit_clears_coordinates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _customer(db_session)
    created = await _add(client, user)
    address = await db_session.get(Address, created["id"])
    assert address is not None
    address.latitude, address.longitude = 34.0, -118.0
    await db_session.flush()
    url = f"/me/addresses/{created['id']}"

    await client.patch(url, json={"delivery_instructions": "Gate code 1234"}, headers=auth(user))
    await db_session.refresh(address)
    assert address.latitude == 34.0  # same place, coordinates still valid

    await client.patch(url, json={"postal_code": "90002"}, headers=auth(user))
    await db_session.refresh(address)
    assert address.latitude is None and address.longitude is None


async def test_validation(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await _customer(db_session)

    missing = await client.post("/me/addresses", json={"line1": "1 St"}, headers=auth(user))
    assert missing.status_code == 422
    assert {"city", "state", "postal_code"} <= set(missing.json()["error"]["fields"])

    blank = await client.post(
        "/me/addresses", json={**HOME, "line1": "   ", "postal_code": "x" * 21}, headers=auth(user)
    )
    assert blank.status_code == 422
    assert {"line1", "postal_code"} <= set(blank.json()["error"]["fields"])

    # Optional fields: blank becomes null.
    created = await _add(client, user, line2="  ", delivery_instructions="")
    assert created["line2"] is None and created["delivery_instructions"] is None

    url = f"/me/addresses/{created['id']}"
    null_required = await client.patch(url, json={"city": None}, headers=auth(user))
    assert null_required.status_code == 422


async def test_address_limit(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await _customer(db_session)
    for i in range(MAX_ADDRESSES):
        db_session.add(
            Address(user_id=user.id, line1=f"{i} St", city="C", state="CA", postal_code="1")
        )
    await db_session.flush()

    response = await client.post("/me/addresses", json=HOME, headers=auth(user))
    assert response.status_code == 409


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/me/addresses")).status_code == 401
