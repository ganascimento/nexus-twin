import uuid

import pytest
from sqlalchemy import select

from src.database.models.factory import Factory
from src.database.models.truck import Truck


pytestmark = pytest.mark.asyncio


def _unique_name(prefix: str = "cross") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_factory(client, name: str | None = None) -> dict:
    name = name or _unique_name("factory")
    resp = await client.post(
        "/entities/factories/", json={"name": name, "lat": -23.55, "lng": -46.63}
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_warehouse(client, name: str | None = None) -> dict:
    name = name or _unique_name("wh")
    resp = await client.post(
        "/entities/warehouses/",
        json={
            "name": name,
            "lat": -23.55,
            "lng": -46.63,
            "region": "Test Region",
            "capacity_total": 500.0,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_store(client, name: str | None = None) -> dict:
    name = name or _unique_name("store")
    resp = await client.post(
        "/entities/stores/",
        json={"name": name, "lat": -23.55, "lng": -46.63},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_truck(
    client, factory_id: str | None = None
) -> dict:
    resp = await client.post(
        "/entities/trucks/",
        json={
            "name": _unique_name("truck"),
            "truck_type": "proprietario" if factory_id else "terceiro",
            "lat": -23.55,
            "lng": -46.63,
            "capacity_tons": 15.0,
            "factory_id": factory_id,
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_factory_then_delete_confirms_removal(client, async_session):
    created = await _create_factory(client)
    factory_id = created["id"]

    resp = await client.delete(f"/entities/factories/{factory_id}")
    assert resp.status_code == 200

    row = (
        await async_session.execute(
            select(Factory).where(Factory.id == factory_id)
        )
    ).scalar_one_or_none()

    assert row is None


async def test_create_truck_linked_to_factory(client, async_session):
    factory = await _create_factory(client)
    truck = await _create_truck(client, factory_id=factory["id"])

    row = (
        await async_session.execute(
            select(Truck).where(Truck.id == truck["id"])
        )
    ).scalar_one()

    assert row.factory_id == factory["id"]


async def test_delete_factory_unlinks_truck(client, async_session):
    factory = await _create_factory(client)
    truck = await _create_truck(client, factory_id=factory["id"])

    resp = await client.delete(f"/entities/factories/{factory['id']}")
    assert resp.status_code == 200

    truck_row = (
        await async_session.execute(
            select(Truck).where(Truck.id == truck["id"])
        )
    ).scalar_one()

    assert truck_row is not None
    assert truck_row.factory_id is None


async def test_multiple_entities_coexist(client, async_session):
    await _create_factory(client)
    await _create_warehouse(client)
    await _create_store(client)
    await _create_truck(client)

    factories_resp = await client.get("/entities/factories/")
    warehouses_resp = await client.get("/entities/warehouses/")
    stores_resp = await client.get("/entities/stores/")
    trucks_resp = await client.get("/entities/trucks/")

    assert factories_resp.status_code == 200
    assert len(factories_resp.json()) >= 1

    assert warehouses_resp.status_code == 200
    assert len(warehouses_resp.json()) >= 1

    assert stores_resp.status_code == 200
    assert len(stores_resp.json()) >= 1

    assert trucks_resp.status_code == 200
    assert len(trucks_resp.json()) >= 1
