"""What customers see when browsing restaurants and menus (epic4.task4).

These are separate from the merchant schemas on purpose: a field added for merchants
later (costs, internal notes, sort order) never shows up here unless it's added here
too.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import MenuItem, MenuItemModifier, ModifierOption, Restaurant
from app.schemas.availability import HoursWindow
from app.services.availability import Window, is_accepting_orders, is_open


def _availability(restaurant: Restaurant, windows: list[Window], now: datetime) -> dict[str, bool]:
    return {
        "is_open_now": is_open(windows, restaurant.timezone, now),
        "accepting_orders": is_accepting_orders(restaurant, windows, now),
    }


class RestaurantSummaryOut(BaseModel):
    id: int
    name: str
    address: str
    is_open_now: bool
    # Active, open and not paused: whether checkout will take an order right now.
    accepting_orders: bool

    @classmethod
    def build(
        cls, restaurant: Restaurant, windows: list[Window], now: datetime
    ) -> "RestaurantSummaryOut":
        return cls(
            id=restaurant.id,
            name=restaurant.name,
            address=restaurant.address,
            **_availability(restaurant, windows, now),
        )


class RestaurantDetailOut(RestaurantSummaryOut):
    timezone: str
    hours: list[HoursWindow]

    @classmethod
    def build(
        cls, restaurant: Restaurant, windows: list[Window], now: datetime
    ) -> "RestaurantDetailOut":
        return cls(
            id=restaurant.id,
            name=restaurant.name,
            address=restaurant.address,
            timezone=restaurant.timezone,
            hours=[HoursWindow.of(w) for w in windows],
            **_availability(restaurant, windows, now),
        )


class OptionOut(BaseModel):
    id: int
    name: str
    price_delta: Decimal

    @classmethod
    def of(cls, option: ModifierOption) -> "OptionOut":
        return cls(id=option.id, name=option.name, price_delta=option.price_delta)


class ModifierOut(BaseModel):
    id: int
    name: str
    min_selections: int
    max_selections: int | None
    options: list[OptionOut]

    @classmethod
    def of(cls, modifier: MenuItemModifier) -> "ModifierOut":
        return cls(
            id=modifier.id,
            name=modifier.name,
            min_selections=modifier.min_selections,
            max_selections=modifier.max_selections,
            options=[OptionOut.of(o) for o in modifier.options],
        )


class MenuItemOut(BaseModel):
    id: int
    name: str
    description: str | None
    price: Decimal
    photo_url: str | None
    # False while the restaurant has 86'd it: shown, but can't be ordered.
    is_available: bool
    modifiers: list[ModifierOut]

    @classmethod
    def of(cls, item: MenuItem) -> "MenuItemOut":
        return cls(
            id=item.id,
            name=item.name,
            description=item.description,
            price=item.price,
            photo_url=item.photo_url,
            is_available=item.is_available,
            modifiers=[ModifierOut.of(m) for m in item.modifiers],
        )


class CategoryOut(BaseModel):
    id: int
    name: str
    items: list[MenuItemOut]


class MenuOut(BaseModel):
    restaurant: RestaurantDetailOut
    categories: list[CategoryOut]
    uncategorized_items: list[MenuItemOut]
