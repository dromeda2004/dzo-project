"""Loading a restaurant's menu, shared by the merchant menu (epic3.task3) and the
customer menu (epic4.task4) so both see the same items in the same order."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MenuCategory, MenuItem, MenuItemModifier

ITEM_TREE = selectinload(MenuItem.modifiers).selectinload(MenuItemModifier.options)


async def load_menu(
    db: AsyncSession, restaurant_id: int
) -> tuple[list[MenuCategory], dict[int | None, list[MenuItem]]]:
    """The restaurant's categories in display order, and its non-archived items (with
    modifiers and options loaded) grouped by category id; None holds uncategorized."""
    categories = await db.scalars(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == restaurant_id)
        .order_by(MenuCategory.sort_order, MenuCategory.id)
    )
    items = await db.scalars(
        select(MenuItem)
        .options(ITEM_TREE)
        .where(MenuItem.restaurant_id == restaurant_id, MenuItem.is_archived.is_(False))
        .order_by(MenuItem.sort_order, MenuItem.id)
        .execution_options(populate_existing=True)
    )
    by_category: defaultdict[int | None, list[MenuItem]] = defaultdict(list)
    for item in items:
        by_category[item.category_id].append(item)
    return list(categories), by_category
