import asyncio
import os
import pathlib
import threading

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent


def _asyncpg_url(url: str) -> str:
    for prefix in ("postgresql+psycopg2://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


def _run_in_thread(func) -> None:
    exc_holder: list = []

    def _target():
        try:
            func()
        except Exception as exc:
            exc_holder.append(exc)

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if exc_holder:
        raise exc_holder[0]


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as container:
        yield container


@pytest.fixture(scope="session")
def db_url(postgres_container):
    return _asyncpg_url(postgres_container.get_connection_url())


@pytest.fixture(scope="session")
def alembic_cfg(db_url):
    os.environ["DATABASE_URL"] = db_url
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "src" / "database" / "migrations"))
    return cfg


@pytest.fixture(scope="session")
def async_engine(alembic_cfg, db_url):
    _run_in_thread(lambda: command.upgrade(alembic_cfg, "head"))
    engine = create_async_engine(db_url, poolclass=NullPool)
    yield engine
    _run_in_thread(lambda: command.downgrade(alembic_cfg, "base"))


@pytest.fixture
async def async_session(async_engine):
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def seeded_db(async_engine, db_url):
    from src.database.seed import seed_default_world

    def _run_seed():
        async def _seed():
            engine = create_async_engine(db_url, poolclass=NullPool)
            try:
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    await seed_default_world(session)
                    await session.commit()
            finally:
                await engine.dispose()

        asyncio.run(_seed())

    _run_in_thread(_run_seed)
    yield
