"""Restaurant discovery and the customer menu (epic4.task4)."""

from datetime import UTC, datetime, time
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    ModifierOption,
    Restaurant,
    RestaurantHours,
    User,
)
from tests.factories import auth, create_restaurant, create_user


async def _customer(db: AsyncSession) -> User:
    return await create_user(db, email="browser@example.com")


async def _open_all_week(db: AsyncSession, restaurant: Restaurant) -> None:
    db.add_all(
        RestaurantHours(
            restaurant_id=restaurant.id, day_of_week=d, opens_at=time(0), closes_at=time(0)
        )
        for d in range(7)
    )
    await db.flush()


async def _menu(db: AsyncSession, restaurant: Restaurant) -> dict[str, MenuItem]:
    """Two categories (the second shown first), an empty category, an uncategorized
    item, an 86'd item and an archived one."""
    mains = MenuCategory(restaurant_id=restaurant.id, name="Mains", sort_order=2)
    drinks = MenuCategory(restaurant_id=restaurant.id, name="Drinks", sort_order=1)
    empty = MenuCategory(restaurant_id=restaurant.id, name="Desserts", sort_order=3)
    db.add_all([mains, drinks, empty])
    await db.flush()

    burger = MenuItem(
        restaurant_id=restaurant.id,
        category_id=mains.id,
        name="Burger",
        description="Beef",
        price=Decimal("12.50"),
        modifiers=[
            MenuItemModifier(
                name="Size",
                min_selections=1,
                max_selections=1,
                options=[
                    ModifierOption(name="Regular", price_delta=Decimal("0.00"), sort_order=0),
                    ModifierOption(name="Large", price_delta=Decimal("2.00"), sort_order=1),
                ],
            )
        ],
    )
    soda = MenuItem(
        restaurant_id=restaurant.id, category_id=drinks.id, name="Soda", price=Decimal("2.00")
    )
    sold_out = MenuItem(
        restaurant_id=restaurant.id,
        category_id=mains.id,
        name="Special",
        price=Decimal("15.00"),
        is_available=False,
        sort_order=1,
    )
    archived = MenuItem(
        restaurant_id=restaurant.id,
        category_id=mains.id,
        name="Old item",
        price=Decimal("9.00"),
        is_archived=True,
    )
    loose = MenuItem(restaurant_id=restaurant.id, name="Bread", price=Decimal("3.00"))
    db.add_all([burger, soda, sold_out, archived, loose])
    await db.flush()
    return {"burger": burger, "soda": soda, "sold_out": sold_out, "archived": archived}


async def test_list_shows_active_restaurants_accepting_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    customer = await _customer(db_session)
    closed = await create_restaurant(db_session, "Aardvark Cafe")  # no hours: closed
    open_b = await create_restaurant(db_session, "Bistro")
    open_a = await create_restaurant(db_session, "Annex")
    paused = await create_restaurant(db_session, "Paused Place")
    inactive = await create_restaurant(db_session, "Gone")
    for r in (open_a, open_b, paused):
        await _open_all_week(db_session, r)
    paused.orders_paused_at = datetime.now(UTC)
    inactive.is_active = False
    await db_session.flush()

    response = await client.get("/food/restaurants", headers=auth(customer))

    assert response.status_code == 200
    rows = [
        r
        for r in response.json()
        if r["id"] in {closed.id, open_a.id, open_b.id, paused.id, inactive.id}
    ]
    assert [r["name"] for r in rows] == ["Annex", "Bistro", "Aardvark Cafe", "Paused Place"]
    by_name = {r["name"]: r for r in rows}
    assert by_name["Annex"]["accepting_orders"] is True
    assert by_name["Aardvark Cafe"]["is_open_now"] is False
    assert by_name["Paused Place"] == {
        "id": paused.id,
        "name": "Paused Place",
        "address": paused.address,
        "is_open_now": True,
        "accepting_orders": False,
    }


async def test_menu_for_customers(client: AsyncClient, db_session: AsyncSession) -> None:
    customer = await _customer(db_session)
    restaurant = await create_restaurant(db_session, "Grill")
    await _open_all_week(db_session, restaurant)
    items = await _menu(db_session, restaurant)

    response = await client.get(f"/food/restaurants/{restaurant.id}/menu", headers=auth(customer))

    assert response.status_code == 200
    body = response.json()
    assert body["restaurant"]["name"] == "Grill"
    assert body["restaurant"]["accepting_orders"] is True
    assert len(body["restaurant"]["hours"]) == 7

    # Category order follows sort_order; the empty category is left out.
    assert [c["name"] for c in body["categories"]] == ["Drinks", "Mains"]
    mains = body["categories"][1]["items"]
    # The archived item never appears; the 86'd one does, marked unavailable.
    assert [i["name"] for i in mains] == ["Burger", "Special"]
    assert mains[1]["is_available"] is False
    assert [i["name"] for i in body["uncategorized_items"]] == ["Bread"]

    burger = mains[0]
    assert burger == {
        "id": items["burger"].id,
        "name": "Burger",
        "description": "Beef",
        "price": "12.50",
        "photo_url": None,
        "is_available": True,
        "modifiers": [
            {
                "id": burger["modifiers"][0]["id"],
                "name": "Size",
                "min_selections": 1,
                "max_selections": 1,
                "options": [
                    {
                        "id": burger["modifiers"][0]["options"][0]["id"],
                        "name": "Regular",
                        "price_delta": "0.00",
                    },
                    {
                        "id": burger["modifiers"][0]["options"][1]["id"],
                        "name": "Large",
                        "price_delta": "2.00",
                    },
                ],
            }
        ],
    }


async def test_menu_hides_merchant_only_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    customer = await _customer(db_session)
    restaurant = await create_restaurant(db_session)
    await _menu(db_session, restaurant)

    body = (
        await client.get(f"/food/restaurants/{restaurant.id}/menu", headers=auth(customer))
    ).json()

    text = str(body)
    for merchant_field in ("sort_order", "is_archived", "category_id", "orders_paused_at"):
        assert merchant_field not in text


async def test_inactive_or_unknown_restaurant_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    customer = await _customer(db_session)
    restaurant = await create_restaurant(db_session)
    restaurant.is_active = False
    await db_session.flush()

    for restaurant_id in (restaurant.id, 999_999_999):
        response = await client.get(
            f"/food/restaurants/{restaurant_id}/menu", headers=auth(customer)
        )
        assert response.status_code == 404


async def test_closed_restaurant_menu_is_still_readable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    customer = await _customer(db_session)
    restaurant = await create_restaurant(db_session)  # no hours
    await _menu(db_session, restaurant)

    response = await client.get(f"/food/restaurants/{restaurant.id}/menu", headers=auth(customer))

    assert response.status_code == 200
    assert response.json()["restaurant"]["accepting_orders"] is False
    assert response.json()["categories"]


async def test_browsing_requires_login(client: AsyncClient, db_session: AsyncSession) -> None:
    restaurant = await create_restaurant(db_session)
    assert (await client.get("/food/restaurants")).status_code == 401
    assert (await client.get(f"/food/restaurants/{restaurant.id}/menu")).status_code == 401
