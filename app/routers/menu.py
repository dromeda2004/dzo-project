from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_restaurant_role
from app.core.database import get_db
from app.models import MenuCategory, MenuItem, MenuItemModifier, ModifierOption, Restaurant
from app.models.enums import RestaurantStaffRole
from app.schemas.menu import (
    AvailabilityUpdate,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CategoryWithItemsOut,
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    MenuOut,
    ModifierCreate,
    ModifierOut,
    ModifierUpdate,
    OptionCreate,
    OptionOut,
    OptionUpdate,
)

router = APIRouter(prefix="/restaurants/{restaurant_id}/menu", tags=["menu"])

# Owners and managers build the menu; any staff member can read it and 86 an item.
editor = require_restaurant_role(RestaurantStaffRole.MANAGER)
any_staff = require_restaurant_role(RestaurantStaffRole.STAFF)

_ITEM_TREE = selectinload(MenuItem.modifiers).selectinload(MenuItemModifier.options)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _new_modifier(payload: ModifierCreate) -> MenuItemModifier:
    return MenuItemModifier(
        **payload.model_dump(exclude={"options"}),
        options=[ModifierOption(**o.model_dump()) for o in payload.options],
    )


# Every lookup below filters on restaurant_id (through the item for modifiers and
# options), so an id belonging to another restaurant is a 404, not a cross-tenant edit.


async def _get_category(db: AsyncSession, restaurant_id: int, category_id: int) -> MenuCategory:
    category = await db.scalar(
        select(MenuCategory).where(
            MenuCategory.id == category_id, MenuCategory.restaurant_id == restaurant_id
        )
    )
    if category is None:
        raise _not_found("Category")
    return category


async def _check_category(db: AsyncSession, restaurant_id: int, category_id: int | None) -> None:
    if category_id is not None:
        try:
            await _get_category(db, restaurant_id, category_id)
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="category_id is not a category on this restaurant's menu",
            ) from exc


async def _get_item(db: AsyncSession, restaurant_id: int, item_id: int) -> MenuItem:
    item = await db.scalar(
        select(MenuItem)
        .options(_ITEM_TREE)
        .where(
            MenuItem.id == item_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_archived.is_(False),
        )
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise _not_found("Menu item")
    return item


async def _get_modifier(db: AsyncSession, restaurant_id: int, modifier_id: int) -> MenuItemModifier:
    modifier = await db.scalar(
        select(MenuItemModifier)
        .join(MenuItem)
        .options(selectinload(MenuItemModifier.options))
        .where(
            MenuItemModifier.id == modifier_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_archived.is_(False),
        )
    )
    if modifier is None:
        raise _not_found("Modifier")
    return modifier


async def _get_option(db: AsyncSession, restaurant_id: int, option_id: int) -> ModifierOption:
    option = await db.scalar(
        select(ModifierOption)
        .join(MenuItemModifier)
        .join(MenuItem)
        .where(
            ModifierOption.id == option_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_archived.is_(False),
        )
    )
    if option is None:
        raise _not_found("Option")
    return option


# --- Full menu -------------------------------------------------------------------------


@router.get("", response_model=MenuOut)
async def get_menu(
    restaurant: Restaurant = Depends(any_staff), db: AsyncSession = Depends(get_db)
) -> MenuOut:
    categories = await db.scalars(
        select(MenuCategory)
        .where(MenuCategory.restaurant_id == restaurant.id)
        .order_by(MenuCategory.sort_order, MenuCategory.id)
    )
    items = await db.scalars(
        select(MenuItem)
        .options(_ITEM_TREE)
        .where(MenuItem.restaurant_id == restaurant.id, MenuItem.is_archived.is_(False))
        .order_by(MenuItem.sort_order, MenuItem.id)
        .execution_options(populate_existing=True)
    )
    by_category: defaultdict[int | None, list[MenuItemOut]] = defaultdict(list)
    for item in items:
        by_category[item.category_id].append(MenuItemOut.model_validate(item))
    return MenuOut(
        categories=[
            CategoryWithItemsOut(
                id=c.id, name=c.name, sort_order=c.sort_order, items=by_category[c.id]
            )
            for c in categories
        ],
        uncategorized_items=by_category[None],
    )


# --- Categories ------------------------------------------------------------------------


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuCategory:
    category = MenuCategory(restaurant_id=restaurant.id, **payload.model_dump())
    db.add(category)
    await db.commit()
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuCategory:
    category = await _get_category(db, restaurant.id, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.commit()
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The category's items stay on the menu, uncategorized (ON DELETE SET NULL)."""
    category = await _get_category(db, restaurant.id, category_id)
    await db.delete(category)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Items -----------------------------------------------------------------------------


@router.post("/items", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: MenuItemCreate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuItem:
    await _check_category(db, restaurant.id, payload.category_id)
    item = MenuItem(
        restaurant_id=restaurant.id,
        **payload.model_dump(exclude={"modifiers"}),
        modifiers=[_new_modifier(m) for m in payload.modifiers],
    )
    db.add(item)
    await db.commit()
    return item


@router.patch("/items/{item_id}", response_model=MenuItemOut)
async def update_item(
    item_id: int,
    payload: MenuItemUpdate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuItem:
    item = await _get_item(db, restaurant.id, item_id)
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        await _check_category(db, restaurant.id, changes["category_id"])
    for field, value in changes.items():
        setattr(item, field, value)
    await db.commit()
    return item


@router.put("/items/{item_id}/availability", response_model=MenuItemOut)
async def set_item_availability(
    item_id: int,
    payload: AvailabilityUpdate,
    restaurant: Restaurant = Depends(any_staff),
    db: AsyncSession = Depends(get_db),
) -> MenuItem:
    """The 86 toggle. Open to all staff, since it's the most common change during service."""
    item = await _get_item(db, restaurant.id, item_id)
    item.is_available = payload.is_available
    await db.commit()
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_item(
    item_id: int,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Archives rather than deletes: past order_items still point at this row."""
    item = await _get_item(db, restaurant.id, item_id)
    item.is_archived = True
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Modifiers -------------------------------------------------------------------------


@router.post(
    "/items/{item_id}/modifiers", response_model=ModifierOut, status_code=status.HTTP_201_CREATED
)
async def create_modifier(
    item_id: int,
    payload: ModifierCreate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuItemModifier:
    item = await _get_item(db, restaurant.id, item_id)
    modifier = _new_modifier(payload)
    item.modifiers.append(modifier)
    await db.commit()
    return modifier


@router.patch("/modifiers/{modifier_id}", response_model=ModifierOut)
async def update_modifier(
    modifier_id: int,
    payload: ModifierUpdate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> MenuItemModifier:
    modifier = await _get_modifier(db, restaurant.id, modifier_id)
    changes = payload.model_dump(exclude_unset=True)
    min_selections = changes.get("min_selections", modifier.min_selections)
    max_selections = changes.get("max_selections", modifier.max_selections)
    if max_selections is not None and max_selections < max(min_selections, 1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="max_selections must be at least 1 and at least min_selections",
        )
    for field, value in changes.items():
        setattr(modifier, field, value)
    await db.commit()
    return modifier


@router.delete("/modifiers/{modifier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modifier(
    modifier_id: int,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """A hard delete (with its options): order_items snapshot modifiers, not reference them."""
    modifier = await _get_modifier(db, restaurant.id, modifier_id)
    await db.delete(modifier)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Options ---------------------------------------------------------------------------


@router.post(
    "/modifiers/{modifier_id}/options",
    response_model=OptionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_option(
    modifier_id: int,
    payload: OptionCreate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> ModifierOption:
    modifier = await _get_modifier(db, restaurant.id, modifier_id)
    option = ModifierOption(**payload.model_dump())
    modifier.options.append(option)
    await db.commit()
    return option


@router.patch("/options/{option_id}", response_model=OptionOut)
async def update_option(
    option_id: int,
    payload: OptionUpdate,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> ModifierOption:
    option = await _get_option(db, restaurant.id, option_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, field, value)
    await db.commit()
    return option


@router.delete("/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_option(
    option_id: int,
    restaurant: Restaurant = Depends(editor),
    db: AsyncSession = Depends(get_db),
) -> Response:
    option = await _get_option(db, restaurant.id, option_id)
    await db.delete(option)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
