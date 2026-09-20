import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool (rather than the app's pooled engine in app.core.database) so every test
# gets a fresh asyncpg connection bound to its own event loop — pytest-asyncio's
# default function-scoped loop means a pooled connection from a prior test's loop
# can't be reused and raises "Event loop is closed" / "operation in progress".
_test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_TestSessionLocal = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """A DB session for a single test, rolled back afterwards so tests don't leak state."""
    async with _TestSessionLocal() as session:
        yield session
        await session.rollback()
