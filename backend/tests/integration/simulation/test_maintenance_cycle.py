import asyncio
import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    AGENT_SETTLE_TIME,
    advance_ticks_with_settle,
    get_truck_status,
    make_llm_responses,
)
from src.world.physics import calculate_maintenance_ticks

pytestmark = pytest.mark.asyncio


TRUCK_ID = "truck-006"


async def _inject_truck_wake_event(session, truck_id: str, tick: int) -> None:
    await session.execute(
        text(
            "INSERT INTO events (id, event_type, source, entity_type, entity_id, payload, status, tick_start) "
            "VALUES (gen_random_uuid(), 'truck_breakdown', 'test', 'truck', :tid, '{}'::jsonb, 'active', :tick)"
        ),
        {"tid": truck_id, "tick": tick},
    )


async def _set_truck_degradation(session, truck_id: str, degradation: float) -> None:
    await session.execute(
        text("UPDATE trucks SET degradation=:d WHERE id=:tid"),
        {"d": degradation, "tid": truck_id},
    )


async def _get_maintenance_info(session, truck_id: str) -> tuple[int | None, int | None, float]:
    result = await session.execute(
        text(
            "SELECT maintenance_start_tick, maintenance_duration_ticks, degradation "
            "FROM trucks WHERE id=:tid"
        ),
        {"tid": truck_id},
    )
    row = result.one()
    return row[0], row[1], row[2]


async def test_maintenance_entry_and_exit(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    target_degradation = 0.75
    await _set_truck_degradation(session, TRUCK_ID, target_degradation)
    await _inject_truck_wake_event(session, TRUCK_ID, tick=0)
    await session.commit()

    maintenance_llm = make_llm_responses({
        "action": "request_maintenance",
        "payload": {"current_degradation": target_degradation},
        "reasoning_summary": "Degradation above threshold",
    })
    with patch("src.agents.base.ChatOpenAI", return_value=maintenance_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    status_after_entry = await get_truck_status(session, TRUCK_ID)
    assert status_after_entry == "maintenance"

    start_tick, duration_ticks, degradation_after = await _get_maintenance_info(
        session, TRUCK_ID
    )
    assert start_tick is not None
    assert duration_ticks is not None
    assert degradation_after == pytest.approx(0.0)

    hold_llm = make_llm_responses({
        "action": "hold",
        "payload": None,
        "reasoning_summary": "Stable",
    })
    ticks_to_run = duration_ticks + 5
    with patch("src.agents.base.ChatOpenAI", return_value=hold_llm):
        await advance_ticks_with_settle(client, ticks_to_run)

    await session.rollback()
    status_after_exit = await get_truck_status(session, TRUCK_ID)
    assert status_after_exit == "idle"


async def test_maintenance_duration_matches_degradation(
    seeded_simulation_client, mock_valhalla
):
    client, session, mock_redis = seeded_simulation_client

    target_degradation = 0.75
    expected_duration = calculate_maintenance_ticks(target_degradation)

    await _set_truck_degradation(session, TRUCK_ID, target_degradation)
    await _inject_truck_wake_event(session, TRUCK_ID, tick=0)
    await session.commit()

    maintenance_llm = make_llm_responses({
        "action": "request_maintenance",
        "payload": {"current_degradation": target_degradation},
        "reasoning_summary": "Degradation above threshold",
    })
    with patch("src.agents.base.ChatOpenAI", return_value=maintenance_llm):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()
    _, duration_ticks, _ = await _get_maintenance_info(session, TRUCK_ID)
    assert duration_ticks == expected_duration
