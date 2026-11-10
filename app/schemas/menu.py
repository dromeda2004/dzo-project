from decimal import Decimal
from typing import Annotated, ClassVar, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.schemas.base import ORMBase, PatchModel

CENTS = Decimal("0.01")
# Matches Numeric(10, 2) on menu_items.price and modifier_options.price_delta.
# Serialized as a string ("12.50") so no client ever sees a float. Quantized so a
# create response ("12.5" in) reads the same as the stored value ("12.50" out).
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=2),
    AfterValidator(lambda value: value.quantize(CENTS)),
]
Name = Annotated[str, Field(min_length=1, max_length=255)]
SortOrder = Annotated[int, Field(ge=0)]
PhotoUrl = Annotated[str, Field(max_length=500, pattern=r"^https?://")]
Selections = Annotated[int, Field(ge=0)]


def _check_selection_limits(min_selections: int | None, max_selections: int | None) -> None:
    if max_selections is None:
        return
    if max_selections < 1:
        raise ValueError("max_selections must be at least 1, or null for no limit")
    if min_selections is not None and max_selections < min_selections:
        raise ValueError("max_selections must be at least min_selections")


# --- Categories --------------------------------------------------------------------


class CategoryCreate(BaseModel):
    name: Name
    sort_order: SortOrder = 0


class CategoryUpdate(PatchModel):
    name: Name | None = None
    sort_order: SortOrder | None = None


class CategoryOut(ORMBase):
    id: int
    name: str
    sort_order: int


# --- Modifier options ----------------------------------------------------------------


class OptionCreate(BaseModel):
    name: Name
    price_delta: Money = Decimal("0.00")
    sort_order: SortOrder = 0


class OptionUpdate(PatchModel):
    name: Name | None = None
    price_delta: Money | None = None
    sort_order: SortOrder | None = None


class OptionOut(ORMBase):
    id: int
    name: str
    price_delta: Decimal
    sort_order: int


# --- Modifiers -----------------------------------------------------------------------


class ModifierCreate(BaseModel):
    """`max_selections` null means no upper limit. A required single choice such as
    'Size' is min 1 / max 1; 'up to 3 toppings' is min 0 / max 3."""

    name: Name
    min_selections: Selections = 0
    max_selections: Selections | None = None
    sort_order: SortOrder = 0
    options: list[OptionCreate] = []

    @model_validator(mode="after")
    def _limits(self) -> Self:
        _check_selection_limits(self.min_selections, self.max_selections)
        return self


class ModifierUpdate(PatchModel):
    """Limits are re-checked against the stored values in the route, since a PATCH
    may change only one of them. Null `max_selections` removes the upper limit."""

    clearable: ClassVar[frozenset[str]] = frozenset({"max_selections"})

    name: Name | None = None
    min_selections: Selections | None = None
    max_selections: Selections | None = None
    sort_order: SortOrder | None = None


class ModifierOut(ORMBase):
    id: int
    name: str
    min_selections: int
    max_selections: int | None
    sort_order: int
    options: list[OptionOut]


# --- Items ---------------------------------------------------------------------------


class MenuItemCreate(BaseModel):
    name: Name
    price: Money
    description: str | None = Field(default=None, max_length=1000)
    photo_url: PhotoUrl | None = None
    category_id: int | None = None
    sort_order: SortOrder = 0
    is_available: bool = True
    modifiers: list[ModifierCreate] = []


class MenuItemUpdate(PatchModel):
    """Modifiers are edited through their own endpoints, not here. Null clears
    `description`, `photo_url`, or `category_id`."""

    clearable: ClassVar[frozenset[str]] = frozenset({"description", "photo_url", "category_id"})

    name: Name | None = None
    price: Money | None = None
    description: str | None = Field(default=None, max_length=1000)
    photo_url: PhotoUrl | None = None
    category_id: int | None = None
    sort_order: SortOrder | None = None
    is_available: bool | None = None


class AvailabilityUpdate(BaseModel):
    is_available: bool


class MenuItemOut(ORMBase):
    id: int
    category_id: int | None
    name: str
    description: str | None
    price: Decimal
    photo_url: str | None
    sort_order: int
    is_available: bool
    modifiers: list[ModifierOut]


# --- Full menu -----------------------------------------------------------------------


class CategoryWithItemsOut(CategoryOut):
    items: list[MenuItemOut]


class MenuOut(BaseModel):
    """The whole menu in one read: categories in order, each with its items, then the
    items not in any category. Archived items are left out; 86'd items are included
    with `is_available: false`."""

    categories: list[CategoryWithItemsOut]
    uncategorized_items: list[MenuItemOut]
