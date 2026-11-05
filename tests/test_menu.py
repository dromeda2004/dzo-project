from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Address, MenuItem, Order, OrderItem, Restaurant, User
from app.models.enums import RestaurantStaffRole
from tests.factories import add_staff, auth, create_user, staffed_restaurant

BURGER: dict[str, Any] = {
    "name": "Burger",
    "price": "12.50",
    "description": "Beef patty",
    "modifiers": [
        {
            "name": "Size",
            "min_selections": 1,
            "max_selections": 1,
            "options": [{"name": "Regular"}, {"name": "Double", "price_delta": "4.00"}],
        }
    ],
}


def _menu_url(restaurant: Restaurant, path: str = "") -> str:
    return f"/restaurants/{restaurant.id}/menu{path}"


async def _create_item(
    client: AsyncClient, restaurant: Restaurant, user: User, **overrides: Any
) -> dict[str, Any]:
    response = await client.post(
        _menu_url(restaurant, "/items"), json={**BURGER, **overrides}, headers=auth(user)
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def _get_menu(client: AsyncClient, restaurant: Restaurant, user: User) -> dict[str, Any]:
    response = await client.get(_menu_url(restaurant), headers=auth(user))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --- Building and reading a menu -------------------------------------------------------


async def test_manager_builds_menu_and_reads_it_back(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, manager = await staffed_restaurant(db_session, RestaurantStaffRole.MANAGER)
    category = await client.post(
        _menu_url(restaurant, "/categories"), json={"name": "Mains"}, headers=auth(manager)
    )
    assert category.status_code == 201
    category_id = category.json()["id"]

    created = await _create_item(client, restaurant, manager, category_id=category_id)
    assert created["price"] == "12.50"
    assert [o["name"] for o in created["modifiers"][0]["options"]] == ["Regular", "Double"]

    menu = await _get_menu(client, restaurant, manager)
    assert menu["uncategorized_items"] == []
    [mains] = menu["categories"]
    assert mains["name"] == "Mains"
    [item] = mains["items"]
    assert item == created
    size = item["modifiers"][0]
    assert (size["min_selections"], size["max_selections"]) == (1, 1)
    assert size["options"][1]["price_delta"] == "4.00"


async def test_menu_follows_sort_order(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    for name, order in [("Drinks", 2), ("Mains", 1)]:
        await client.post(
            _menu_url(restaurant, "/categories"),
            json={"name": name, "sort_order": order},
            headers=auth(owner),
        )
    await _create_item(client, restaurant, owner, name="Fries", sort_order=2, modifiers=[])
    item = await _create_item(client, restaurant, owner, name="Burger", sort_order=1, modifiers=[])
    for name, order in [("Toppings", 5), ("Size", 0)]:
        await client.post(
            _menu_url(restaurant, f"/items/{item['id']}/modifiers"),
            json={"name": name, "sort_order": order},
            headers=auth(owner),
        )

    menu = await _get_menu(client, restaurant, owner)

    assert [c["name"] for c in menu["categories"]] == ["Mains", "Drinks"]
    assert [i["name"] for i in menu["uncategorized_items"]] == ["Burger", "Fries"]
    assert [m["name"] for m in menu["uncategorized_items"][0]["modifiers"]] == ["Size", "Toppings"]


# --- Permissions -----------------------------------------------------------------------


async def test_staff_can_read_and_86_but_not_edit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, manager = await staffed_restaurant(db_session, RestaurantStaffRole.MANAGER)
    cook = await create_user(db_session, email="cook@example.com")
    await add_staff(db_session, cook, restaurant, RestaurantStaffRole.STAFF)
    item = await _create_item(client, restaurant, manager)

    await _get_menu(client, restaurant, cook)
    eighty_six = await client.put(
        _menu_url(restaurant, f"/items/{item['id']}/availability"),
        json={"is_available": False},
        headers=auth(cook),
    )
    assert eighty_six.status_code == 200
    assert eighty_six.json()["is_available"] is False
    menu = await _get_menu(client, restaurant, cook)
    assert menu["uncategorized_items"][0]["is_available"] is False

    denied = [
        await client.post(_menu_url(restaurant, "/items"), json=BURGER, headers=auth(cook)),
        await client.patch(
            _menu_url(restaurant, f"/items/{item['id']}"),
            json={"price": "1.00"},
            headers=auth(cook),
        ),
        await client.delete(_menu_url(restaurant, f"/items/{item['id']}"), headers=auth(cook)),
        await client.post(
            _menu_url(restaurant, "/categories"), json={"name": "Mains"}, headers=auth(cook)
        ),
    ]
    assert [r.status_code for r in denied] == [403, 403, 403, 403]


async def test_other_restaurants_staff_cannot_read_menu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    _, rival = await staffed_restaurant(db_session, name="Rival", email="rival@example.com")

    response = await client.get(_menu_url(restaurant), headers=auth(rival))

    assert response.status_code == 403


async def test_ids_from_another_restaurant_are_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A rival owner editing through their own restaurant's URL must not reach our rows."""
    restaurant, owner = await staffed_restaurant(db_session)
    rival_restaurant, rival = await staffed_restaurant(
        db_session, name="Rival", email="rival@example.com"
    )
    item = await _create_item(client, restaurant, owner)
    modifier = item["modifiers"][0]
    option = modifier["options"][0]
    category = (
        await client.post(
            _menu_url(restaurant, "/categories"), json={"name": "Mains"}, headers=auth(owner)
        )
    ).json()

    attempts = [
        await client.patch(
            _menu_url(rival_restaurant, f"/items/{item['id']}"),
            json={"price": "0.01"},
            headers=auth(rival),
        ),
        await client.put(
            _menu_url(rival_restaurant, f"/items/{item['id']}/availability"),
            json={"is_available": False},
            headers=auth(rival),
        ),
        await client.delete(
            _menu_url(rival_restaurant, f"/items/{item['id']}"), headers=auth(rival)
        ),
        await client.post(
            _menu_url(rival_restaurant, f"/items/{item['id']}/modifiers"),
            json={"name": "Sneaky"},
            headers=auth(rival),
        ),
        await client.delete(
            _menu_url(rival_restaurant, f"/modifiers/{modifier['id']}"), headers=auth(rival)
        ),
        await client.patch(
            _menu_url(rival_restaurant, f"/options/{option['id']}"),
            json={"price_delta": "99.00"},
            headers=auth(rival),
        ),
        await client.delete(
            _menu_url(rival_restaurant, f"/categories/{category['id']}"), headers=auth(rival)
        ),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)

    menu = await _get_menu(client, restaurant, owner)
    assert menu["categories"][0]["name"] == "Mains"
    assert menu["uncategorized_items"] == [item]


async def test_item_cannot_use_another_restaurants_category(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    rival_restaurant, rival = await staffed_restaurant(
        db_session, name="Rival", email="rival@example.com"
    )
    rival_category = (
        await client.post(
            _menu_url(rival_restaurant, "/categories"), json={"name": "Theirs"}, headers=auth(rival)
        )
    ).json()

    response = await client.post(
        _menu_url(restaurant, "/items"),
        json={**BURGER, "category_id": rival_category["id"]},
        headers=auth(owner),
    )

    assert response.status_code == 422


# --- Validation ------------------------------------------------------------------------


async def test_invalid_prices_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    for price in ["-1.00", "1.005", "123456789.00"]:
        response = await client.post(
            _menu_url(restaurant, "/items"),
            json={**BURGER, "price": price},
            headers=auth(owner),
        )
        assert response.status_code == 422, price
        assert "price" in response.json()["error"]["fields"]

    negative_option = await client.post(
        _menu_url(restaurant, "/items"),
        json={
            **BURGER,
            "modifiers": [{"name": "Size", "options": [{"name": "S", "price_delta": "-1"}]}],
        },
        headers=auth(owner),
    )
    assert negative_option.status_code == 422


async def test_price_is_stored_exactly(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner, price="0.10")

    stored = await db_session.get(MenuItem, item["id"])

    assert stored is not None
    assert stored.price == Decimal("0.10")


async def test_photo_url_must_be_http(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.post(
        _menu_url(restaurant, "/items"),
        json={**BURGER, "photo_url": "javascript:alert(1)"},
        headers=auth(owner),
    )

    assert response.status_code == 422


async def test_explicit_null_rejected_for_required_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner)

    for field in ["name", "price", "is_available"]:
        response = await client.patch(
            _menu_url(restaurant, f"/items/{item['id']}"),
            json={field: None},
            headers=auth(owner),
        )
        assert response.status_code == 422, field

    cleared = await client.patch(
        _menu_url(restaurant, f"/items/{item['id']}"),
        json={"description": None},
        headers=auth(owner),
    )
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None


async def test_modifier_selection_limits(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner, modifiers=[])
    url = _menu_url(restaurant, f"/items/{item['id']}/modifiers")

    for limits in [{"min_selections": 2, "max_selections": 1}, {"max_selections": 0}]:
        response = await client.post(url, json={"name": "Bad", **limits}, headers=auth(owner))
        assert response.status_code == 422, limits

    toppings = await client.post(
        url, json={"name": "Toppings", "max_selections": 3}, headers=auth(owner)
    )
    assert toppings.status_code == 201
    modifier_url = _menu_url(restaurant, f"/modifiers/{toppings.json()['id']}")

    # min above the stored max is caught even though the PATCH only sends min.
    too_high = await client.patch(modifier_url, json={"min_selections": 4}, headers=auth(owner))
    assert too_high.status_code == 422

    unlimited = await client.patch(modifier_url, json={"max_selections": None}, headers=auth(owner))
    assert unlimited.status_code == 200
    assert unlimited.json()["max_selections"] is None

    required = await client.patch(modifier_url, json={"min_selections": 4}, headers=auth(owner))
    assert required.status_code == 200
    assert required.json()["min_selections"] == 4


# --- Updating and removing -------------------------------------------------------------


async def test_update_item_category_and_price(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner)
    category = (
        await client.post(
            _menu_url(restaurant, "/categories"), json={"name": "Mains"}, headers=auth(owner)
        )
    ).json()

    response = await client.patch(
        _menu_url(restaurant, f"/items/{item['id']}"),
        json={"category_id": category["id"], "price": "13.00"},
        headers=auth(owner),
    )

    assert response.status_code == 200
    menu = await _get_menu(client, restaurant, owner)
    [moved] = menu["categories"][0]["items"]
    assert moved["price"] == "13.00"
    assert moved["modifiers"] == item["modifiers"]


async def test_deleting_category_keeps_its_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    category = (
        await client.post(
            _menu_url(restaurant, "/categories"), json={"name": "Mains"}, headers=auth(owner)
        )
    ).json()
    item = await _create_item(client, restaurant, owner, category_id=category["id"])

    response = await client.delete(
        _menu_url(restaurant, f"/categories/{category['id']}"), headers=auth(owner)
    )

    assert response.status_code == 204
    menu = await _get_menu(client, restaurant, owner)
    assert menu["categories"] == []
    assert [i["id"] for i in menu["uncategorized_items"]] == [item["id"]]
    assert menu["uncategorized_items"][0]["category_id"] is None


async def test_archived_item_leaves_menu_but_order_history_resolves(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner)
    customer = await create_user(db_session, email="customer@example.com")
    address = Address(
        user_id=customer.id, line1="1 Elm St", city="Springfield", state="CA", postal_code="90000"
    )
    db_session.add(address)
    await db_session.flush()
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        delivery_address_id=address.id,
        subtotal=Decimal("12.50"),
    )
    db_session.add(order)
    await db_session.flush()
    order_item = OrderItem(
        order_id=order.id, menu_item_id=item["id"], price_at_order_time=Decimal("12.50")
    )
    db_session.add(order_item)
    await db_session.flush()

    response = await client.delete(
        _menu_url(restaurant, f"/items/{item['id']}"), headers=auth(owner)
    )

    assert response.status_code == 204
    menu = await _get_menu(client, restaurant, owner)
    assert menu["uncategorized_items"] == []
    archived = await db_session.get(MenuItem, order_item.menu_item_id)
    assert archived is not None
    assert archived.is_archived is True
    assert archived.name == "Burger"

    edit = await client.patch(
        _menu_url(restaurant, f"/items/{item['id']}"), json={"price": "1.00"}, headers=auth(owner)
    )
    assert edit.status_code == 404


async def test_add_update_and_delete_modifiers_and_options(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    restaurant, owner = await staffed_restaurant(db_session)
    item = await _create_item(client, restaurant, owner)
    size = item["modifiers"][0]

    added = await client.post(
        _menu_url(restaurant, f"/modifiers/{size['id']}/options"),
        json={"name": "Triple", "price_delta": "7.00", "sort_order": 9},
        headers=auth(owner),
    )
    assert added.status_code == 201
    renamed = await client.patch(
        _menu_url(restaurant, f"/options/{size['options'][0]['id']}"),
        json={"name": "Single"},
        headers=auth(owner),
    )
    assert renamed.status_code == 200
    removed = await client.delete(
        _menu_url(restaurant, f"/options/{size['options'][1]['id']}"), headers=auth(owner)
    )
    assert removed.status_code == 204

    menu = await _get_menu(client, restaurant, owner)
    options = menu["uncategorized_items"][0]["modifiers"][0]["options"]
    assert [(o["name"], o["price_delta"]) for o in options] == [
        ("Single", "0.00"),
        ("Triple", "7.00"),
    ]

    gone = await client.delete(
        _menu_url(restaurant, f"/modifiers/{size['id']}"), headers=auth(owner)
    )
    assert gone.status_code == 204
    menu = await _get_menu(client, restaurant, owner)
    assert menu["uncategorized_items"][0]["modifiers"] == []


async def test_unknown_item_is_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant, owner = await staffed_restaurant(db_session)

    response = await client.patch(
        _menu_url(restaurant, "/items/999999"), json={"price": "1.00"}, headers=auth(owner)
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Menu item not found"
