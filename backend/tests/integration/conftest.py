import pytest
import httpx
from httpx import ASGITransport

from src.main import app
from src.database.session import get_db
from src.database.seed import seed_default_world


@pytest.fixture
async def client(async_session):
    async def _override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_client(async_session):
    await seed_default_world(async_session)
    await async_session.flush()

    async def _override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as c:
        yield c
    app.dependency_overrides.clear()
