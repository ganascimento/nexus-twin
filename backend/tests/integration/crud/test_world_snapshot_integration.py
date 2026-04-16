import pytest


pytestmark = pytest.mark.asyncio


async def test_snapshot_returns_all_seeded_factories(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["factories"]) == 3


async def test_snapshot_returns_all_seeded_warehouses(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["warehouses"]) == 3


async def test_snapshot_returns_all_seeded_stores(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["stores"]) == 5


async def test_snapshot_returns_all_seeded_trucks(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["trucks"]) == 6


async def test_snapshot_contains_factory_products(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    for factory in data["factories"]:
        assert isinstance(factory["products"], dict)
        assert len(factory["products"]) > 0


async def test_snapshot_contains_warehouse_stocks(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    for warehouse in data["warehouses"]:
        assert isinstance(warehouse["stocks"], dict)
        assert len(warehouse["stocks"]) > 0


async def test_snapshot_contains_store_stocks(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    for store in data["stores"]:
        assert isinstance(store["stocks"], dict)
        assert len(store["stocks"]) > 0


async def test_snapshot_factory_coordinates(seeded_client):
    resp = await seeded_client.get("/world/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    factory_001 = next(
        (f for f in data["factories"] if f["id"] == "factory-001"), None
    )
    assert factory_001 is not None
    assert abs(factory_001["lat"] - (-22.9099)) < 0.01
    assert abs(factory_001["lng"] - (-47.0626)) < 0.01
