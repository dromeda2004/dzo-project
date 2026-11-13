import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MenuItem,
    MenuItemModifier,
    ModifierOption,
    Order,
    OrderItem,
    Restaurant,
    RestaurantStaff,
    User,
)
from app.models.enums import OrderStatus
from scripts.seed_dev import (
    SEED_PLACED_ORDERS,
    NotLocalDatabaseError,
    assert_local_database,
    seed,
)

COUNTED = [User, Restaurant, RestaurantStaff, MenuItem, MenuItemModifier, ModifierOption]


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://dzo:dzo@localhost:5432/dzo",
        "postgresql+asyncpg://dzo:dzo@127.0.0.1/dzo",
        "postgresql+asyncpg://dzo:dzo@[::1]:5432/dzo",
        "postgresql+asyncpg://dzo:dzo@/dzo",
    ],
)
def test_local_database_urls_are_allowed(url: str) -> None:
    assert_local_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://dzo:dzo@db.prod.internal:5432/dzo",
        "postgresql+asyncpg://dzo:dzo@10.0.0.5/dzo",
        "postgresql+asyncpg://dzo:dzo@localhost.evil.com/dzo",
    ],
)
def test_non_local_database_urls_are_refused(url: str) -> None:
    with pytest.raises(NotLocalDatabaseError):
        assert_local_database(url)


async def _counts(db: AsyncSession) -> dict[str, int]:
    counts = {}
    for model in [*COUNTED, Order, OrderItem]:
        counts[model.__name__] = await db.scalar(select(func.count()).select_from(model)) or 0
    return counts


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed(db_session)
    after_first = await _counts(db_session)

    second = await seed(db_session)
    assert second.created == {}
    assert second.restaurant_id == first.restaurant_id
    assert await _counts(db_session) == after_first


async def test_seed_creates_placed_orders_and_tops_them_up(db_session: AsyncSession) -> None:
    summary = await seed(db_session)

    def placed():
        return select(Order).where(
            Order.restaurant_id == summary.restaurant_id, Order.status == OrderStatus.PLACED
        )

    orders = (await db_session.scalars(placed())).all()
    assert len(orders) == SEED_PLACED_ORDERS

    # Walking one order forward leaves room for exactly one fresh Placed order.
    orders[0].status = OrderStatus.ACKNOWLEDGED
    await db_session.flush()
    again = await seed(db_session)
    assert again.created == {"orders": 1}
    assert len((await db_session.scalars(placed())).all()) == SEED_PLACED_ORDERS
