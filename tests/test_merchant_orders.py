from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Address, MenuItem, Order, OrderItem, Restaurant, User
from app.models.enums import CancellationReason, OrderStatus, RestaurantStaffRole
from app.services.order_lifecycle import transition
from tests.factories import (
    auth,
    create_driver,
    create_order,
    create_restaurant,
    create_user,
    staffed_restaurant,
)

S = OrderStatus


def url(restaurant: Restaurant, suffix: str = "") -> str:
    return f"/restaurants/{restaurant.id}/orders{suffix}"


async def order_with_items(
    db: AsyncSession, restaurant: Restaurant, email: str
) -> tuple[Order, MenuItem]:
    """A Placed order for a 2x burger with a modifier and 1x fries. Returns the order
    and the burger menu item."""
    burger = MenuItem(restaurant_id=restaurant.id, name="Burger", price=Decimal("10.00"))
    fries = MenuItem(restaurant_id=restaurant.id, name="Fries", price=Decimal("4.00"))
    db.add_all([burger, fries])
    await db.flush()

    order = await create_order(db, restaurant, customer_email=email)
    # Loaded explicitly: async sessions can't lazy-load relationships.
    customer = await db.get(User, order.customer_id)
    address = await db.get(Address, order.delivery_address_id)
    assert customer is not None and address is not None
    customer.full_name = "Casey Q. Customer"
    customer.phone = "+15550001111"
    address.delivery_instructions = "Leave at the front desk"
    db.add_all(
        [
            OrderItem(
                order_id=order.id,
                menu_item_id=burger.id,
                quantity=2,
                price_at_order_time=Decimal("12.00"),
                selected_modifiers={"Size": [{"name": "Double", "price_delta": "2.00"}]},
            ),
            OrderItem(
                order_id=order.id,
                menu_item_id=fries.id,
                quantity=1,
                price_at_order_time=Decimal("4.00"),
            ),
        ]
    )
    await db.flush()
    return order, burger


# --- Inbox list ----------------------------------------------------------------------


async def test_inbox_shows_active_orders_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    placed = await create_order(db_session, restaurant, customer_email="a@example.com")
    claimed = await create_order(
        db_session, restaurant, status=S.CLAIMED, customer_email="b@example.com"
    )
    await create_order(db_session, restaurant, status=S.DELIVERED, customer_email="c@example.com")
    cancelled = await create_order(db_session, restaurant, customer_email="d@example.com")
    await transition(
        db_session, cancelled, S.CANCELLED, cancellation_reason=CancellationReason.TOO_BUSY
    )

    response = await client.get(url(restaurant), headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert [o["id"] for o in body["orders"]] == [claimed.id, placed.id]
    assert body["next_before"] is None
    assert body["orders"][1] == {
        "id": placed.id,
        "status": "placed",
        "created_at": body["orders"][1]["created_at"],
        "customer_first_name": "Test",
        "item_count": 0,
        "subtotal": "10.00",
        "prep_time_estimate_minutes": None,
        "ready_time": None,
    }


async def test_inbox_filters_by_status(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    await create_order(db_session, restaurant, customer_email="a@example.com")
    delivered = await create_order(
        db_session, restaurant, status=S.DELIVERED, customer_email="b@example.com"
    )
    claimed = await create_order(
        db_session, restaurant, status=S.CLAIMED, customer_email="c@example.com"
    )

    one = await client.get(url(restaurant), params={"status": "delivered"}, headers=auth(staff))
    assert [o["id"] for o in one.json()["orders"]] == [delivered.id]

    several = await client.get(
        url(restaurant),
        params=[("status", "delivered"), ("status", "claimed")],
        headers=auth(staff),
    )
    assert [o["id"] for o in several.json()["orders"]] == [claimed.id, delivered.id]

    bad = await client.get(url(restaurant), params={"status": "lost"}, headers=auth(staff))
    assert bad.status_code == 422


async def test_inbox_counts_items_by_quantity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    await order_with_items(db_session, restaurant, "a@example.com")

    response = await client.get(url(restaurant), headers=auth(staff))

    [row] = response.json()["orders"]
    assert (row["item_count"], row["customer_first_name"]) == (3, "Casey")


async def test_inbox_pages_by_order_id(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    ids = [
        (await create_order(db_session, restaurant, customer_email=f"c{i}@example.com")).id
        for i in range(5)
    ]
    newest_first = ids[::-1]

    first = (await client.get(url(restaurant), params={"limit": 2}, headers=auth(staff))).json()
    assert [o["id"] for o in first["orders"]] == newest_first[:2]
    assert first["next_before"] == newest_first[1]

    # An order arriving between polls doesn't shift the next page.
    await create_order(db_session, restaurant, customer_email="late@example.com")

    second = (
        await client.get(
            url(restaurant),
            params={"limit": 2, "before": first["next_before"]},
            headers=auth(staff),
        )
    ).json()
    assert [o["id"] for o in second["orders"]] == newest_first[2:4]

    last = (
        await client.get(
            url(restaurant),
            params={"limit": 2, "before": second["next_before"]},
            headers=auth(staff),
        )
    ).json()
    assert [o["id"] for o in last["orders"]] == newest_first[4:]
    assert last["next_before"] is None


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"before": 0}])
async def test_inbox_rejects_bad_paging(
    client: AsyncClient, db_session: AsyncSession, params: dict
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    response = await client.get(url(restaurant), params=params, headers=auth(staff))
    assert response.status_code == 422


# --- Order detail --------------------------------------------------------------------


async def test_detail_shows_items_as_ordered_not_todays_menu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order, burger = await order_with_items(db_session, restaurant, "a@example.com")
    # The menu price changes after the order was placed.
    burger.price = Decimal("99.00")
    await db_session.flush()

    response = await client.get(url(restaurant, f"/{order.id}"), headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [
        {
            "id": body["items"][0]["id"],
            "menu_item_id": burger.id,
            "name": "Burger",
            "quantity": 2,
            "price_at_order_time": "12.00",
            "line_total": "24.00",
            "selected_modifiers": {"Size": [{"name": "Double", "price_delta": "2.00"}]},
        },
        {
            "id": body["items"][1]["id"],
            "menu_item_id": body["items"][1]["menu_item_id"],
            "name": "Fries",
            "quantity": 1,
            "price_at_order_time": "4.00",
            "line_total": "4.00",
            "selected_modifiers": None,
        },
    ]
    assert body["delivery_address"] == {
        "line1": "1 Test St",
        "line2": None,
        "city": "Springfield",
        "state": "CA",
        "postal_code": "90000",
        "delivery_instructions": "Leave at the front desk",
    }
    assert (body["status"], body["driver"], body["cancellation_reason"]) == ("placed", None, None)


async def test_detail_exposes_only_the_customers_first_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order, _ = await order_with_items(db_session, restaurant, "private@example.com")

    detail = await client.get(url(restaurant, f"/{order.id}"), headers=auth(staff))
    inbox = await client.get(url(restaurant), headers=auth(staff))

    assert detail.json()["customer"] == {"first_name": "Casey"}
    for response in (detail, inbox):
        text = response.text
        assert "private@example.com" not in text
        assert "+15550001111" not in text
        assert "Customer" not in text  # last name
        assert "customer_id" not in text


async def test_detail_shows_the_claimed_driver(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(
        db_session, restaurant, status=S.OPEN_FOR_CLAIM, customer_email="a@example.com"
    )
    driver = await create_driver(db_session, email="dana@example.com")
    driver_user = await db_session.get(User, driver.user_id)
    assert driver_user is not None
    driver_user.full_name = "Dana Driver"
    driver.vehicle_description = "Silver Civic"
    await transition(db_session, order, S.CLAIMED, driver_id=driver.id)

    body = (await client.get(url(restaurant, f"/{order.id}"), headers=auth(staff))).json()

    assert body["status"] == "claimed"
    assert body["claimed_at"] is not None
    assert body["driver"] == {
        "id": driver.id,
        "first_name": "Dana",
        "vehicle_description": "Silver Civic",
    }
    assert "dana@example.com" not in str(body)


async def test_detail_shows_why_an_order_was_cancelled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    order = await create_order(db_session, restaurant, customer_email="a@example.com")
    await transition(
        db_session,
        order,
        S.CANCELLED,
        cancellation_reason=CancellationReason.ITEM_UNAVAILABLE,
        cancellation_note="Out of fish",
    )

    body = (await client.get(url(restaurant, f"/{order.id}"), headers=auth(staff))).json()

    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None
    assert (body["cancellation_reason"], body["cancellation_note"]) == (
        "item_unavailable",
        "Out of fish",
    )


# --- Who can see what ----------------------------------------------------------------


@pytest.mark.parametrize("role", list(RestaurantStaffRole))
async def test_every_staff_role_can_read_the_inbox(
    client: AsyncClient, db_session: AsyncSession, role: RestaurantStaffRole
) -> None:
    restaurant, member = await staffed_restaurant(db_session, role)
    order = await create_order(db_session, restaurant, customer_email="a@example.com")

    assert (await client.get(url(restaurant), headers=auth(member))).status_code == 200
    detail = await client.get(url(restaurant, f"/{order.id}"), headers=auth(member))
    assert detail.status_code == 200


async def test_admin_can_read_any_inbox(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant = await create_restaurant(db_session)
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)
    order = await create_order(db_session, restaurant, customer_email="a@example.com")

    assert (await client.get(url(restaurant), headers=auth(admin))).status_code == 200
    detail = await client.get(url(restaurant, f"/{order.id}"), headers=auth(admin))
    assert detail.status_code == 200


async def test_other_restaurants_orders_are_hidden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF, name="Mine")
    theirs = await create_restaurant(db_session, "Theirs")
    my_order = await create_order(db_session, mine, customer_email="a@example.com")
    their_order = await create_order(db_session, theirs, customer_email="b@example.com")

    # Their inbox: not on that restaurant's staff.
    assert (await client.get(url(theirs), headers=auth(staff))).status_code == 403
    assert (
        await client.get(url(theirs, f"/{their_order.id}"), headers=auth(staff))
    ).status_code == 403

    # Their order through my restaurant's path: doesn't exist here.
    response = await client.get(url(mine, f"/{their_order.id}"), headers=auth(staff))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"

    # My inbox only lists my orders.
    inbox = await client.get(url(mine), headers=auth(staff))
    assert [o["id"] for o in inbox.json()["orders"]] == [my_order.id]


async def test_staff_of_another_restaurant_and_customers_are_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant = await create_restaurant(db_session, "Pilot")
    elsewhere, outsider = await staffed_restaurant(
        db_session, RestaurantStaffRole.OWNER, name="Elsewhere", email="owner2@example.com"
    )
    order = await create_order(db_session, restaurant, customer_email="cust@example.com")
    customer = await db_session.get(User, order.customer_id)
    assert customer is not None

    for user in (outsider, customer):
        assert (await client.get(url(restaurant), headers=auth(user))).status_code == 403

    assert (await client.get(url(restaurant))).status_code == 401


async def test_unknown_order_and_restaurant_are_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, staff = await staffed_restaurant(db_session, RestaurantStaffRole.STAFF)
    assert (await client.get(url(restaurant, "/999999999"), headers=auth(staff))).status_code == 404
    admin = await create_user(db_session, email="admin@example.com", is_admin=True)
    assert (
        await client.get("/restaurants/999999999/orders", headers=auth(admin))
    ).status_code == 404
