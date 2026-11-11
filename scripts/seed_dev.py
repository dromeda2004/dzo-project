"""Populates a local database with dev data for manual walk-throughs (epic3.task4).

Seeds an admin, a pilot restaurant with an owner, a manager and a staff member,
a menu (categories, items, modifiers, one 86'd item), a customer with a delivery
address, a driver, and orders in the Placed state. Orders can't be created through
the API until Epic 4, so this is how task6–task8 get something to walk through.

    make seed            # or: python -m scripts.seed_dev

Safe to re-run: every row is looked up by a natural key (email, restaurant name,
category/item name) before being created, so a second run adds nothing. The one
exception is orders: each run tops the restaurant up to SEED_PLACED_ORDERS orders
in the Placed state, so after walking some through the lifecycle, re-running gives
you fresh ones to work with.

Refuses to run unless DATABASE_URL points at localhost. Every seeded account uses
the dev-only password below; never point this at a shared database.
"""

import asyncio
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    Address,
    DriverProfile,
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    ModifierOption,
    Order,
    OrderItem,
    Restaurant,
    RestaurantStaff,
    User,
)
from app.models.enums import OrderStatus, RestaurantStaffRole

# Dev-only. Documented in README.md; shared by every seeded account.
SEED_PASSWORD = "dzo-dev-only"
SEED_PLACED_ORDERS = 3
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

RESTAURANT_NAME = "DZO Pilot Kitchen"
ADMIN_EMAIL = "admin@dzo.test"
CUSTOMER_EMAIL = "customer@dzo.test"
DRIVER_EMAIL = "driver@dzo.test"
STAFF = [
    ("owner@dzo.test", "Olivia Owner", RestaurantStaffRole.OWNER),
    ("manager@dzo.test", "Marco Manager", RestaurantStaffRole.MANAGER),
    ("staff@dzo.test", "Sam Staff", RestaurantStaffRole.STAFF),
]

# category -> items. Each item: (name, description, price, available, modifiers),
# each modifier: (name, min, max, [(option, price_delta)]).
MENU: dict[str, list[tuple[str, str, str, bool, list[Any]]]] = {
    "Mains": [
        (
            "Classic Burger",
            "Beef patty, lettuce, tomato, house sauce",
            "12.50",
            True,
            [
                ("Size", 1, 1, [("Regular", "0.00"), ("Double", "4.00")]),
                ("Add-ons", 0, 3, [("Cheese", "1.00"), ("Bacon", "2.00"), ("Avocado", "1.50")]),
            ],
        ),
        ("Chicken Bowl", "Grilled chicken, rice, greens", "13.00", True, []),
        # 86'd, so the availability toggle has something to flip back.
        ("Fish Tacos", "Two tacos, slaw, lime crema", "11.00", False, []),
    ],
    "Sides": [
        ("Fries", "Skin-on, sea salt", "4.00", True, []),
    ],
    "Drinks": [
        (
            "Lemonade",
            "Fresh-squeezed",
            "3.50",
            True,
            [("Size", 1, 1, [("Small", "0.00"), ("Large", "1.00")])],
        ),
    ],
}


class NotLocalDatabaseError(RuntimeError):
    pass


def assert_local_database(database_url: str) -> None:
    """Raise unless the URL's host is this machine. A missing host (unix socket) counts
    as local; anything else, including a docker-compose service name, does not."""
    host = make_url(database_url).host
    if host is not None and host not in LOCAL_HOSTS:
        raise NotLocalDatabaseError(
            f"Refusing to seed: DATABASE_URL host is {host!r}, expected one of "
            f"{sorted(LOCAL_HOSTS)}. The seed only runs against a local database."
        )


@dataclass
class SeedSummary:
    created: dict[str, int] = field(default_factory=dict)
    restaurant_id: int = 0

    def count(self, kind: str) -> None:
        self.created[kind] = self.created.get(kind, 0) + 1


async def _get_or_create_user(
    session: AsyncSession,
    summary: SeedSummary,
    password_hash: str,
    email: str,
    full_name: str,
    *,
    is_admin: bool = False,
) -> User:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        user = User(
            email=email, full_name=full_name, password_hash=password_hash, is_admin=is_admin
        )
        session.add(user)
        await session.flush()
        summary.count("users")
    return user


async def _seed_menu(session: AsyncSession, summary: SeedSummary, restaurant: Restaurant) -> None:
    for cat_index, (category_name, items) in enumerate(MENU.items()):
        category = await session.scalar(
            select(MenuCategory).where(
                MenuCategory.restaurant_id == restaurant.id, MenuCategory.name == category_name
            )
        )
        if category is None:
            category = MenuCategory(
                restaurant_id=restaurant.id, name=category_name, sort_order=cat_index
            )
            session.add(category)
            await session.flush()
            summary.count("menu_categories")

        for item_index, (name, description, price, available, modifiers) in enumerate(items):
            exists = await session.scalar(
                select(MenuItem.id).where(
                    MenuItem.restaurant_id == restaurant.id, MenuItem.name == name
                )
            )
            if exists is not None:
                continue
            # Modifiers are only built alongside a new item, so a re-run never
            # duplicates them and never undoes edits made through the API.
            item = MenuItem(
                restaurant_id=restaurant.id,
                category_id=category.id,
                name=name,
                description=description,
                price=Decimal(price),
                is_available=available,
                sort_order=item_index,
                modifiers=[
                    MenuItemModifier(
                        name=mod_name,
                        min_selections=min_sel,
                        max_selections=max_sel,
                        sort_order=mod_index,
                        options=[
                            ModifierOption(
                                name=opt_name, price_delta=Decimal(delta), sort_order=opt_index
                            )
                            for opt_index, (opt_name, delta) in enumerate(options)
                        ],
                    )
                    for mod_index, (mod_name, min_sel, max_sel, options) in enumerate(modifiers)
                ],
            )
            session.add(item)
            await session.flush()
            summary.count("menu_items")


async def _menu_item(session: AsyncSession, restaurant: Restaurant, name: str) -> MenuItem:
    item = await session.scalar(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id, MenuItem.name == name)
    )
    if item is None:
        raise RuntimeError(f"Seed menu item {name!r} is missing; was it renamed or deleted?")
    return item


async def _seed_orders(
    session: AsyncSession,
    summary: SeedSummary,
    restaurant: Restaurant,
    customer: User,
    address: Address,
) -> None:
    placed = await session.scalar(
        select(func.count(Order.id)).where(
            Order.restaurant_id == restaurant.id, Order.status == OrderStatus.PLACED
        )
    )
    burger = await _menu_item(session, restaurant, "Classic Burger")
    fries = await _menu_item(session, restaurant, "Fries")
    lemonade = await _menu_item(session, restaurant, "Lemonade")

    # (menu item, quantity, unit price incl. modifiers, selected_modifiers snapshot)
    baskets: list[list[tuple[MenuItem, int, Decimal, dict[str, Any] | None]]] = [
        [
            (
                burger,
                1,
                burger.price + Decimal("1.00"),
                {
                    "Size": [{"name": "Regular", "price_delta": "0.00"}],
                    "Add-ons": [{"name": "Cheese", "price_delta": "1.00"}],
                },
            ),
            (fries, 1, fries.price, None),
        ],
        [
            (
                lemonade,
                2,
                lemonade.price + Decimal("1.00"),
                {"Size": [{"name": "Large", "price_delta": "1.00"}]},
            )
        ],
        [
            (
                burger,
                2,
                burger.price + Decimal("4.00"),
                {"Size": [{"name": "Double", "price_delta": "4.00"}], "Add-ons": []},
            ),
            (fries, 2, fries.price, None),
        ],
    ]

    for i in range(max(0, SEED_PLACED_ORDERS - (placed or 0))):
        basket = baskets[i % len(baskets)]
        order = Order(
            customer_id=customer.id,
            restaurant_id=restaurant.id,
            delivery_address_id=address.id,
            status=OrderStatus.PLACED,
            subtotal=sum((unit * qty for _, qty, unit, _ in basket), Decimal("0")),
            tip=Decimal("3.00"),
            items=[
                OrderItem(
                    menu_item_id=item.id,
                    quantity=qty,
                    price_at_order_time=unit,
                    selected_modifiers=mods,
                )
                for item, qty, unit, mods in basket
            ],
        )
        session.add(order)
        await session.flush()
        summary.count("orders")


async def seed(session: AsyncSession) -> SeedSummary:
    """Create whatever seed data is missing. Flushes but doesn't commit."""
    summary = SeedSummary()
    # One hash for every account: bcrypt is deliberately slow.
    password_hash = hash_password(SEED_PASSWORD)

    await _get_or_create_user(
        session, summary, password_hash, ADMIN_EMAIL, "Ada Admin", is_admin=True
    )

    restaurant = await session.scalar(select(Restaurant).where(Restaurant.name == RESTAURANT_NAME))
    if restaurant is None:
        restaurant = Restaurant(
            name=RESTAURANT_NAME,
            address="100 Market St, San Francisco, CA 94105",
            timezone="America/Los_Angeles",
        )
        session.add(restaurant)
        await session.flush()
        summary.count("restaurants")
    summary.restaurant_id = restaurant.id

    for email, full_name, role in STAFF:
        user = await _get_or_create_user(session, summary, password_hash, email, full_name)
        membership = await session.scalar(
            select(RestaurantStaff).where(
                RestaurantStaff.user_id == user.id,
                RestaurantStaff.restaurant_id == restaurant.id,
            )
        )
        if membership is None:
            session.add(RestaurantStaff(user_id=user.id, restaurant_id=restaurant.id, role=role))
            await session.flush()
            summary.count("restaurant_staff")

    await _seed_menu(session, summary, restaurant)

    customer = await _get_or_create_user(
        session, summary, password_hash, CUSTOMER_EMAIL, "Casey Customer"
    )
    address = await session.scalar(
        select(Address).where(Address.user_id == customer.id).order_by(Address.id).limit(1)
    )
    if address is None:
        address = Address(
            user_id=customer.id,
            line1="500 Howard St",
            line2="Apt 4",
            city="San Francisco",
            state="CA",
            postal_code="94105",
            delivery_instructions="Leave at the front desk",
        )
        session.add(address)
        await session.flush()
        summary.count("addresses")

    driver = await _get_or_create_user(session, summary, password_hash, DRIVER_EMAIL, "Dana Driver")
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == driver.id))
    if profile is None:
        session.add(
            DriverProfile(
                user_id=driver.id,
                vehicle_description="Silver Honda Civic",
                background_check_status="approved",
            )
        )
        await session.flush()
        summary.count("driver_profiles")

    await _seed_orders(session, summary, restaurant, customer, address)
    return summary


async def main() -> int:
    settings = get_settings()
    try:
        assert_local_database(settings.database_url)
    except NotLocalDatabaseError as exc:
        print(exc, file=sys.stderr)
        return 1

    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            summary = await seed(session)
            await session.commit()
    finally:
        await engine.dispose()

    if summary.created:
        print("Created: " + ", ".join(f"{n} {kind}" for kind, n in summary.created.items()))
    else:
        print("Nothing to create; seed data already present.")
    print(f"Restaurant {RESTAURANT_NAME!r} has id {summary.restaurant_id}.")
    print(f"Log in as any of the accounts below with password {SEED_PASSWORD!r}:")
    for email in [ADMIN_EMAIL, *(s[0] for s in STAFF), CUSTOMER_EMAIL, DRIVER_EMAIL]:
        print(f"  {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
