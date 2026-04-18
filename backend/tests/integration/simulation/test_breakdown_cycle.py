import json
from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from sqlalchemy import text

from tests.integration.simulation.conftest import (
    advance_ticks_with_settle,
    get_truck_status,
)

pytestmark = pytest.mark.asyncio


def _hold_llm():
    return FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=json.dumps(
                    {
                        "action": "hold",
                        "payload": None,
                        "reasoning_summary": "Hold",
                    }
                )
            )
        ]
        * 10
    )


_CARGO_JSON = json.dumps(
    {
        "material_id": "cimento",
        "quantity_tons": 10.0,
        "origin_type": "warehouse",
        "origin_id": "warehouse-002",
        "destination_type": "store",
        "destination_id": "store-001",
    }
)


async def _setup_in_transit_truck(session, truck_id: str):
    await session.execute(
        text(
            """
            UPDATE trucks
            SET status='in_transit',
                degradation=0.85,
                breakdown_risk=0.5,
                cargo=CAST(:cargo AS JSONB),
                current_lat=-23.5,
                current_lng=-46.6
            WHERE id=:tid
            """
        ),
        {"tid": truck_id, "cargo": _CARGO_JSON},
    )
    result = await session.execute(
        text(
            """
            INSERT INTO routes (
                id, truck_id, origin_type, origin_id, dest_type, dest_id,
                path, timestamps, eta_ticks, status, started_at
            )
            VALUES (
                gen_random_uuid(), :tid, 'warehouse', 'warehouse-002',
                'store', 'store-001',
                CAST(:path AS JSONB), CAST(:timestamps AS JSONB),
                10, 'active', NOW()
            )
            RETURNING id
            """
        ),
        {
            "tid": truck_id,
            "path": json.dumps([[-46.6, -23.5], [-46.5, -23.5]]),
            "timestamps": json.dumps([0, 10]),
        },
    )
    route_id = result.scalar_one()
    await session.execute(
        text("UPDATE trucks SET active_route_id=:rid WHERE id=:tid"),
        {"rid": route_id, "tid": truck_id},
    )
    return route_id


async def _get_truck_cargo(session, truck_id: str):
    result = await session.execute(
        text("SELECT cargo FROM trucks WHERE id=:tid"),
        {"tid": truck_id},
    )
    return result.scalar_one_or_none()


async def _count_breakdown_events(session, truck_id: str):
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM events "
            "WHERE event_type='truck_breakdown' "
            "AND entity_type='truck' AND entity_id=:tid"
        ),
        {"tid": truck_id},
    )
    return result.scalar_one()


async def test_breakdown_stops_truck(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _setup_in_transit_truck(session, "truck-006")
    await session.commit()

    with patch("src.world.physics.random.random", return_value=0.0), \
         patch("src.agents.base.ChatOpenAI", return_value=_hold_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    status = await get_truck_status(session, "truck-006")
    assert status == "broken"

    cargo = await _get_truck_cargo(session, "truck-006")
    assert cargo is not None

    breakdown_count = await _count_breakdown_events(session, "truck-006")
    assert breakdown_count >= 1


async def test_broken_truck_cargo_not_lost(seeded_simulation_client, mock_valhalla):
    client, session, mock_redis = seeded_simulation_client

    await _setup_in_transit_truck(session, "truck-006")
    await session.commit()

    with patch("src.world.physics.random.random", return_value=0.0), \
         patch("src.agents.base.ChatOpenAI", return_value=_hold_llm()):
        await advance_ticks_with_settle(client, 1)

    await session.rollback()

    status = await get_truck_status(session, "truck-006")
    assert status == "broken"

    cargo = await _get_truck_cargo(session, "truck-006")
    assert cargo is not None
    assert cargo.get("material_id") == "cimento"
    assert cargo.get("quantity_tons") == 10.0
