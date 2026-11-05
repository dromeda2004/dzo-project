from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import OrderItem
    from app.models.restaurant import Restaurant


class MenuCategory(Base, TimestampMixin):
    """A section of a restaurant's menu, e.g. 'Mains' or 'Drinks'."""

    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_categories")
    # passive_deletes: the database's ON DELETE SET NULL uncategorizes the items,
    # so the ORM doesn't need to load them first.
    items: Mapped[list[MenuItem]] = relationship(back_populates="category", passive_deletes=True)


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), index=True)
    # Deleting a category leaves its items uncategorized rather than deleting them.
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_categories.id", ondelete="SET NULL", name="fk_menu_items_category_id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Archived instead of deleted, since order_items keep pointing at the row.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")
    category: Mapped[MenuCategory | None] = relationship(back_populates="items")
    modifiers: Mapped[list[MenuItemModifier]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by=lambda: (MenuItemModifier.sort_order, MenuItemModifier.id),
    )
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="menu_item")


class MenuItemModifier(Base, TimestampMixin):
    """A customization group on a menu item, e.g. 'Size' (choose exactly 1) or
    'Toppings' (choose up to 3). `max_selections` NULL means no upper limit."""

    __tablename__ = "menu_item_modifiers"
    __table_args__ = (
        CheckConstraint("min_selections >= 0", name="ck_modifier_min_selections_nonnegative"),
        CheckConstraint(
            "max_selections IS NULL OR (max_selections >= 1 AND max_selections >= min_selections)",
            name="ck_modifier_max_selections_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    min_selections: Mapped[int] = mapped_column(default=0, server_default="0")
    max_selections: Mapped[int | None] = mapped_column()
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")

    menu_item: Mapped[MenuItem] = relationship(back_populates="modifiers")
    # Hard-deleting modifiers and options is safe: order_items snapshot them in
    # selected_modifiers instead of referencing them.
    options: Mapped[list[ModifierOption]] = relationship(
        back_populates="modifier",
        cascade="all, delete-orphan",
        order_by=lambda: (ModifierOption.sort_order, ModifierOption.id),
    )


class ModifierOption(Base, TimestampMixin):
    """A single choice within a modifier group, e.g. 'Large' (+$2.00)."""

    __tablename__ = "modifier_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    modifier_id: Mapped[int] = mapped_column(ForeignKey("menu_item_modifiers.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")

    modifier: Mapped[MenuItemModifier] = relationship(back_populates="options")
