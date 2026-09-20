from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import OrderItem
    from app.models.restaurant import Restaurant


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")
    modifiers: Mapped[list[MenuItemModifier]] = relationship(back_populates="menu_item")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="menu_item")


class MenuItemModifier(Base, TimestampMixin):
    """A customization group on a menu item, e.g. 'Size' or 'Add-ons'."""

    __tablename__ = "menu_item_modifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    menu_item: Mapped[MenuItem] = relationship(back_populates="modifiers")
    options: Mapped[list[ModifierOption]] = relationship(back_populates="modifier")


class ModifierOption(Base, TimestampMixin):
    """A single choice within a modifier group, e.g. 'Large' (+$2.00)."""

    __tablename__ = "modifier_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    modifier_id: Mapped[int] = mapped_column(ForeignKey("menu_item_modifiers.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    modifier: Mapped[MenuItemModifier] = relationship(back_populates="options")
