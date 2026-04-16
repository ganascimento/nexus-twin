import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def test_start_simulation(simulation_client):
    resp = await simulation_client.post("/simulation/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
    await simulation_client.post("/simulation/stop")


async def test_status_after_start(simulation_client):
    await simulation_client.post("/simulation/start")
    await asyncio.sleep(0.1)

    resp = await simulation_client.get("/simulation/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"

    await simulation_client.post("/simulation/stop")


async def test_stop_simulation(simulation_client):
    await simulation_client.post("/simulation/start")
    await asyncio.sleep(0.1)

    resp = await simulation_client.post("/simulation/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


async def test_status_after_stop(simulation_client):
    await simulation_client.post("/simulation/start")
    await asyncio.sleep(0.1)
    await simulation_client.post("/simulation/stop")

    resp = await simulation_client.get("/simulation/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "stopped"


async def test_manual_tick_when_stopped(simulation_client):
    resp = await simulation_client.post("/simulation/tick")
    assert resp.status_code == 200
    assert resp.json() == {"status": "advanced", "tick": 1}

    status_resp = await simulation_client.get("/simulation/status")
    assert status_resp.json()["current_tick"] == 1


async def test_two_manual_ticks(simulation_client):
    await simulation_client.post("/simulation/tick")
    await simulation_client.post("/simulation/tick")

    resp = await simulation_client.get("/simulation/status")
    assert resp.json()["current_tick"] == 2


async def test_manual_tick_while_running_is_rejected(simulation_client):
    await simulation_client.post("/simulation/start")
    await asyncio.sleep(0.1)

    with pytest.raises(RuntimeError, match="stop the engine before advancing manually"):
        await simulation_client.post("/simulation/tick")

    await simulation_client.post("/simulation/stop")


async def test_speed_update(simulation_client):
    resp = await simulation_client.patch(
        "/simulation/speed", json={"tick_interval_seconds": 15}
    )
    assert resp.status_code == 200

    status_resp = await simulation_client.get("/simulation/status")
    assert status_resp.json()["tick_interval_seconds"] == 15


async def test_speed_minimum_enforced(simulation_client):
    await simulation_client.patch(
        "/simulation/speed", json={"tick_interval_seconds": 5}
    )

    resp = await simulation_client.get("/simulation/status")
    assert resp.json()["tick_interval_seconds"] == 10
