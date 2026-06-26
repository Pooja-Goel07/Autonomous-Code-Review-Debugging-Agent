from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Setup the async database engine
# Echo SQL queries in development mode for easier debugging
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.BACKEND_ENV == "development"),
    future=True,
)

# Create the sessionmaker factory for async sessions
SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for obtaining an asynchronous database session.
    Yields the session and ensures clean closure after use.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
