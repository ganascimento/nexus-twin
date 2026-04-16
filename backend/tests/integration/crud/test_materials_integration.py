import uuid

import pytest
from sqlalchemy import select

from src.database.models.material import Material


pytestmark = pytest.mark.asyncio


def _unique_name(prefix: str = "mat") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_material(client, name: str | None = None) -> dict:
    name = name or _unique_name()
    resp = await client.post("/materials/", json={"name": name})
    return resp.json()


async def test_create_material(client, async_session):
    name = _unique_name()
    resp = await client.post("/materials/", json={"name": name})

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == name
    assert body["is_active"] is True
    assert "id" in body


async def test_create_material_persists_in_db(client, async_session):
    name = _unique_name()
    body = (await client.post("/materials/", json={"name": name})).json()

    row = (await async_session.execute(
        select(Material).where(Material.id == body["id"])
    )).scalar_one()

    assert row.name == name
    assert row.is_active is True


async def test_list_materials(client, async_session):
    await _create_material(client)
    await _create_material(client)

    resp = await client.get("/materials/")

    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_list_materials_active_only(client, async_session):
    active = await _create_material(client)
    deactivated = await _create_material(client)

    await client.patch(f"/materials/{deactivated['id']}/deactivate")

    resp = await client.get("/materials/", params={"active_only": True})

    assert resp.status_code == 200
    ids = [m["id"] for m in resp.json()]
    assert active["id"] in ids
    assert deactivated["id"] not in ids


async def test_update_material_name(client, async_session):
    original = await _create_material(client)
    new_name = _unique_name("updated")

    resp = await client.patch(
        f"/materials/{original['id']}", json={"name": new_name}
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


async def test_update_material_persists_in_db(client, async_session):
    original = await _create_material(client)
    new_name = _unique_name("updated")

    await client.patch(
        f"/materials/{original['id']}", json={"name": new_name}
    )

    row = (await async_session.execute(
        select(Material).where(Material.id == original["id"])
    )).scalar_one()

    assert row.name == new_name


async def test_update_material_not_found(client, async_session):
    fake_id = f"nonexistent_{uuid.uuid4().hex[:8]}"

    resp = await client.patch(
        f"/materials/{fake_id}", json={"name": "whatever"}
    )

    assert resp.status_code == 404


async def test_deactivate_material(client, async_session):
    material = await _create_material(client)

    resp = await client.patch(f"/materials/{material['id']}/deactivate")

    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_deactivate_material_persists_in_db(client, async_session):
    material = await _create_material(client)

    await client.patch(f"/materials/{material['id']}/deactivate")

    row = (await async_session.execute(
        select(Material).where(Material.id == material["id"])
    )).scalar_one()

    assert row.is_active is False
