import uuid

import pytest
from sqlalchemy import select

from src.database.models.truck import Truck


pytestmark = pytest.mark.asyncio


def _unique_name(prefix: str = "truck") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_truck(
    client,
    truck_type: str = "terceiro",
    lat: float = -23.55,
    lng: float = -46.63,
    capacity_tons: float = 15.0,
) -> dict:
    resp = await client.post(
        "/entities/trucks/",
        json={
            "name": _unique_name(),
            "truck_type": truck_type,
            "lat": lat,
            "lng": lng,
            "capacity_tons": capacity_tons,
        },
    )
    return resp.json()


async def test_create_truck(client, async_session):
    resp = await client.post(
        "/entities/trucks/",
        json={
            "name": _unique_name(),
            "truck_type": "terceiro",
            "lat": -23.55,
            "lng": -46.63,
            "capacity_tons": 15.0,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["truck_type"] == "terceiro"
    assert body["status"] == "idle"
    assert body["degradation"] == 0.0
    assert body["capacity_tons"] == 15.0


async def test_create_truck_persists_in_db(client, async_session):
    body = (
        await client.post(
            "/entities/trucks/",
            json={
                "name": _unique_name(),
                "truck_type": "terceiro",
                "lat": -23.55,
                "lng": -46.63,
                "capacity_tons": 15.0,
            },
        )
    ).json()

    row = (
        await async_session.execute(select(Truck).where(Truck.id == body["id"]))
    ).scalar_one()

    assert row.truck_type == "terceiro"
    assert row.capacity_tons == 15.0
    assert row.base_lat == -23.55
    assert row.base_lng == -46.63
    assert row.current_lat == -23.55
    assert row.current_lng == -46.63
    assert row.status == "idle"


async def test_create_proprietario_truck(client, async_session):
    resp = await client.post(
        "/entities/trucks/",
        json={
            "name": _unique_name(),
            "truck_type": "proprietario",
            "lat": -22.91,
            "lng": -47.06,
            "capacity_tons": 20.0,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["truck_type"] == "proprietario"


async def test_list_trucks(client, async_session):
    await _create_truck(client)
    await _create_truck(client)

    resp = await client.get("/entities/trucks/")

    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_delete_truck(client, async_session):
    created = await _create_truck(client)

    resp = await client.delete(f"/entities/trucks/{created['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}


async def test_delete_truck_removes_from_db(client, async_session):
    created = await _create_truck(client)

    await client.delete(f"/entities/trucks/{created['id']}")

    row = (
        await async_session.execute(select(Truck).where(Truck.id == created["id"]))
    ).scalar_one_or_none()

    assert row is None
