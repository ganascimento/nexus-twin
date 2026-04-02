import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine, AsyncSessionLocal
    if _engine is None:
        database_url = os.environ["DATABASE_URL"]
        _engine = create_async_engine(database_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db():
    _get_engine()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
