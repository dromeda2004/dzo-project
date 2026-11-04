from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app

settings = get_settings()

# NullPool (rather than the app's pooled engine in app.core.database) so every test
# gets a fresh asyncpg connection bound to its own event loop — pytest-asyncio's
# default function-scoped loop means a pooled connection from a prior test's loop
# can't be reused and raises "Event loop is closed" / "operation in progress".
_test_engine = create_async_engine(settings.database_url, poolclass=NullPool)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """A DB session for a single test, rolled back afterwards so tests don't leak state.

    The session runs inside an outer transaction and turns each commit() into a
    savepoint release, so routes that commit (e.g. creating a restaurant) still
    leave nothing behind once the outer transaction rolls back.
    """
    async with _test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An HTTP client for the app, sharing db_session's transaction so anything a
    test sets up directly (e.g. seeding a user) is visible to the request, and
    anything the request writes rolls back with the rest of the test."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
