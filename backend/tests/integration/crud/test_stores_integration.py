import uuid

import pytest
from sqlalchemy import select

from src.database.models.store import Store


pytestmark = pytest.mark.asyncio


def _unique_name(prefix: str = "store") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_store(
    client,
    name: str | None = None,
    lat: float = -23.55,
    lng: float = -46.63,
) -> dict:
    name = name or _unique_name()
    resp = await client.post(
        "/entities/stores/",
        json={"name": name, "lat": lat, "lng": lng},
    )
    return resp.json()


async def test_create_store(client, async_session):
    name = _unique_name()
    resp = await client.post(
        "/entities/stores/",
        json={"name": name, "lat": -23.55, "lng": -46.63},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == name
    assert body["lat"] == -23.55
    assert body["lng"] == -46.63
    assert body["status"] == "open"


async def test_create_store_persists_in_db(client, async_session):
    name = _unique_name()
    body = (await client.post(
        "/entities/stores/",
        json={"name": name, "lat": -23.55, "lng": -46.63},
    )).json()

    row = (await async_session.execute(
        select(Store).where(Store.id == body["id"])
    )).scalar_one()

    assert row.name == name
    assert abs(row.lat - (-23.55)) < 0.0001
    assert abs(row.lng - (-46.63)) < 0.0001
    assert row.status == "open"


async def test_list_stores(client, async_session):
    await _create_store(client)
    await _create_store(client)

    resp = await client.get("/entities/stores/")

    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_store_by_id(client, async_session):
    created = await _create_store(client, name="Get Me Store", lat=-23.10, lng=-46.50)

    resp = await client.get(f"/entities/stores/{created['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Get Me Store"
    assert body["lat"] == -23.10
    assert body["lng"] == -46.50


async def test_get_store_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"
    resp = await client.get(f"/entities/stores/{fake_id}")
    assert resp.status_code == 404


async def test_update_store(client, async_session):
    created = await _create_store(client)
    new_name = _unique_name("updated")

    resp = await client.patch(
        f"/entities/stores/{created['id']}", json={"name": new_name}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


async def test_update_store_persists_in_db(client, async_session):
    created = await _create_store(client)
    new_name = _unique_name("updated")

    await client.patch(
        f"/entities/stores/{created['id']}", json={"name": new_name}
    )

    row = (await async_session.execute(
        select(Store).where(Store.id == created["id"])
    )).scalar_one()

    assert row.name == new_name


async def test_delete_store(client, async_session):
    created = await _create_store(client)

    resp = await client.delete(f"/entities/stores/{created['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}


async def test_delete_store_removes_from_db(client, async_session):
    created = await _create_store(client)

    await client.delete(f"/entities/stores/{created['id']}")

    row = (await async_session.execute(
        select(Store).where(Store.id == created["id"])
    )).scalar_one_or_none()

    assert row is None


async def test_delete_store_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"
    resp = await client.delete(f"/entities/stores/{fake_id}")
    assert resp.status_code == 404
