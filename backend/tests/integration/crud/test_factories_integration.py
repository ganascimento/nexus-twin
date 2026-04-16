import uuid

import pytest
from sqlalchemy import select

from src.database.models.factory import Factory


pytestmark = pytest.mark.asyncio


def _unique_name(prefix: str = "factory") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_factory(client, name: str | None = None, lat: float = -23.55, lng: float = -46.63) -> dict:
    name = name or _unique_name()
    resp = await client.post("/entities/factories/", json={"name": name, "lat": lat, "lng": lng})
    return resp.json()


async def test_create_factory(client, async_session):
    name = _unique_name()
    resp = await client.post("/entities/factories/", json={"name": name, "lat": -23.55, "lng": -46.63})

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == name
    assert body["lat"] == -23.55
    assert body["lng"] == -46.63
    assert body["status"] is not None


async def test_create_factory_persists_in_db(client, async_session):
    name = _unique_name()
    body = (await client.post("/entities/factories/", json={"name": name, "lat": -22.91, "lng": -47.06})).json()

    row = (await async_session.execute(
        select(Factory).where(Factory.id == body["id"])
    )).scalar_one()

    assert row.name == name
    assert abs(row.lat - (-22.91)) < 0.0001
    assert abs(row.lng - (-47.06)) < 0.0001


async def test_list_factories(client, async_session):
    await _create_factory(client)
    await _create_factory(client)

    resp = await client.get("/entities/factories/")

    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_factory_by_id(client, async_session):
    created = await _create_factory(client, name="Get Me Factory", lat=-23.10, lng=-46.50)

    resp = await client.get(f"/entities/factories/{created['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Get Me Factory"
    assert body["lat"] == -23.10
    assert body["lng"] == -46.50


async def test_get_factory_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"

    resp = await client.get(f"/entities/factories/{fake_id}")

    assert resp.status_code == 404


async def test_update_factory(client, async_session):
    created = await _create_factory(client)
    new_name = _unique_name("updated")

    resp = await client.patch(
        f"/entities/factories/{created['id']}", json={"name": new_name}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


async def test_update_factory_persists_in_db(client, async_session):
    created = await _create_factory(client)
    new_name = _unique_name("updated")

    await client.patch(
        f"/entities/factories/{created['id']}", json={"name": new_name}
    )

    row = (await async_session.execute(
        select(Factory).where(Factory.id == created["id"])
    )).scalar_one()

    assert row.name == new_name


async def test_delete_factory(client, async_session):
    created = await _create_factory(client)

    resp = await client.delete(f"/entities/factories/{created['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}


async def test_delete_factory_removes_from_db(client, async_session):
    created = await _create_factory(client)

    await client.delete(f"/entities/factories/{created['id']}")

    row = (await async_session.execute(
        select(Factory).where(Factory.id == created["id"])
    )).scalar_one_or_none()

    assert row is None


async def test_delete_factory_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"

    resp = await client.delete(f"/entities/factories/{fake_id}")

    assert resp.status_code == 404
