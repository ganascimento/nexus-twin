import uuid

import pytest
from sqlalchemy import select

from src.database.models.warehouse import Warehouse


pytestmark = pytest.mark.asyncio

WAREHOUSE_PAYLOAD = {
    "name": "Test WH",
    "lat": -23.55,
    "lng": -46.63,
    "region": "Test Region",
    "capacity_total": 500.0,
}


def _unique_name(prefix: str = "wh") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_warehouse(client, **overrides) -> dict:
    payload = {**WAREHOUSE_PAYLOAD, **overrides}
    if "name" not in overrides:
        payload["name"] = _unique_name()
    resp = await client.post("/entities/warehouses/", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def test_create_warehouse(client, async_session):
    name = _unique_name()
    resp = await client.post(
        "/entities/warehouses/",
        json={**WAREHOUSE_PAYLOAD, "name": name},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == name
    assert body["lat"] == WAREHOUSE_PAYLOAD["lat"]
    assert body["lng"] == WAREHOUSE_PAYLOAD["lng"]
    assert body["region"] == WAREHOUSE_PAYLOAD["region"]
    assert body["capacity_total"] == WAREHOUSE_PAYLOAD["capacity_total"]
    assert "id" in body
    assert "status" in body


async def test_create_warehouse_persists_in_db(client, async_session):
    body = await _create_warehouse(client)

    row = (
        await async_session.execute(
            select(Warehouse).where(Warehouse.id == body["id"])
        )
    ).scalar_one()

    assert row.name == body["name"]
    assert row.lat == body["lat"]
    assert row.lng == body["lng"]
    assert row.region == body["region"]
    assert row.capacity_total == body["capacity_total"]


async def test_list_warehouses(client, async_session):
    await _create_warehouse(client, name=_unique_name("list_a"))
    await _create_warehouse(client, name=_unique_name("list_b"))

    resp = await client.get("/entities/warehouses/")

    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_warehouse_by_id(client, async_session):
    created = await _create_warehouse(client)

    resp = await client.get(f"/entities/warehouses/{created['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == created["name"]
    assert body["lat"] == created["lat"]
    assert body["lng"] == created["lng"]
    assert body["region"] == created["region"]
    assert body["capacity_total"] == created["capacity_total"]


async def test_get_warehouse_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"

    resp = await client.get(f"/entities/warehouses/{fake_id}")

    assert resp.status_code == 404


async def test_update_warehouse(client, async_session):
    created = await _create_warehouse(client)
    new_name = _unique_name("updated")

    resp = await client.patch(
        f"/entities/warehouses/{created['id']}", json={"name": new_name}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


async def test_update_warehouse_persists_in_db(client, async_session):
    created = await _create_warehouse(client)
    new_name = _unique_name("updated")

    await client.patch(
        f"/entities/warehouses/{created['id']}", json={"name": new_name}
    )

    row = (
        await async_session.execute(
            select(Warehouse).where(Warehouse.id == created["id"])
        )
    ).scalar_one()

    assert row.name == new_name


async def test_delete_warehouse(client, async_session):
    created = await _create_warehouse(client)

    resp = await client.delete(f"/entities/warehouses/{created['id']}")

    assert resp.status_code == 200


async def test_delete_warehouse_removes_from_db(client, async_session):
    created = await _create_warehouse(client)

    await client.delete(f"/entities/warehouses/{created['id']}")

    row = (
        await async_session.execute(
            select(Warehouse).where(Warehouse.id == created["id"])
        )
    ).scalar_one_or_none()

    assert row is None


async def test_delete_warehouse_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"

    resp = await client.delete(f"/entities/warehouses/{fake_id}")

    assert resp.status_code == 404
