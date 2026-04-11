from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage

from src.agents.truck_agent import TruckAgent
from src.simulation.events import SimulationEvent


def make_trigger(entity_id: str = "truck-001", event_type: str = "contract_proposal") -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type="truck",
        entity_id=entity_id,
        payload={},
        tick=1,
    )


def make_world_slice(entity: dict | None = None) -> dict:
    return {
        "entity": entity or {
            "id": "truck-001",
            "truck_type": "terceiro",
            "degradation": 0.3,
            "cargo": {},
            "status": "idle",
        },
        "related_entities": [],
        "active_events": [],
        "pending_orders": [],
    }


# ---------------------------------------------------------------------------
# test_run_cycle_completes_full_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cycle_completes_full_path(mock_db_session, mock_publisher):
    agent = TruckAgent("truck-001", mock_db_session, mock_publisher)
    trigger = make_trigger()
    world_slice = make_world_slice()

    llm_response = AIMessage(content='{"action": "accept_contract", "payload": {}}')
    fake_chat = FakeListChatModel(responses=[llm_response])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                    with patch("src.agents.truck_agent.TruckDecision", stub_schema):
                        await agent.run_cycle(trigger)

    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["entity_type"] == "truck"
    assert call_data["entity_id"] == "truck-001"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_truck_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_truck_type(mock_db_session, mock_publisher):
    agent = TruckAgent("truck-001", mock_db_session, mock_publisher)

    mock_truck = MagicMock()
    mock_truck.id = "truck-001"
    mock_truck.truck_type = "terceiro"
    mock_truck.degradation = 0.3
    mock_truck.cargo = {}
    mock_truck.status = "idle"
    mock_truck.active_route_id = None

    mock_truck_repo = AsyncMock()
    mock_truck_repo.get_by_id.return_value = mock_truck

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.truck_agent.TruckRepository", return_value=mock_truck_repo):
        with patch("src.agents.truck_agent.EventRepository", return_value=mock_event_repo):
            world_slice = await agent._build_world_state_slice(current_tick=1)

    entity = world_slice["entity"]
    assert "truck_type" in entity


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_active_route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_active_route(mock_db_session, mock_publisher):
    agent = TruckAgent("truck-001", mock_db_session, mock_publisher)

    mock_truck = MagicMock()
    mock_truck.id = "truck-001"
    mock_truck.truck_type = "proprietario"
    mock_truck.degradation = 0.2
    mock_truck.cargo = {}
    mock_truck.status = "in_transit"
    mock_truck.active_route_id = "route-abc"

    mock_route = MagicMock()
    mock_route.id = "route-abc"

    mock_truck_repo = AsyncMock()
    mock_truck_repo.get_by_id.return_value = mock_truck

    mock_route_repo = AsyncMock()
    mock_route_repo.get_by_id.return_value = mock_route

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.truck_agent.TruckRepository", return_value=mock_truck_repo):
        with patch("src.agents.truck_agent.RouteRepository", return_value=mock_route_repo):
            with patch("src.agents.truck_agent.EventRepository", return_value=mock_event_repo):
                world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["related_entities"]) >= 1
    mock_route_repo.get_by_id.assert_called_once_with("route-abc")


# ---------------------------------------------------------------------------
# test_fast_path_maintenance_when_degradation_critical
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_path_maintenance_when_degradation_critical(mock_db_session, mock_publisher):
    agent = TruckAgent("truck-001", mock_db_session, mock_publisher)
    trigger = make_trigger(event_type="truck_breakdown")

    world_slice = make_world_slice(
        entity={
            "id": "truck-001",
            "truck_type": "terceiro",
            "degradation": 0.95,
            "cargo": {},
            "status": "idle",
        }
    )

    # FakeListChatModel with no responses — will error if LLM is invoked
    fake_chat = FakeListChatModel(responses=[])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                    with patch("src.agents.truck_agent.TruckDecision", stub_schema):
                        final_state = await agent.run_cycle(trigger)

    # Fast path fires: LLM is not called, decision goes through act_node
    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["action"] == "request_maintenance"


# ---------------------------------------------------------------------------
# test_proprietario_does_not_block_on_fast_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proprietario_does_not_block_on_fast_path(mock_db_session, mock_publisher):
    agent = TruckAgent("truck-002", mock_db_session, mock_publisher)
    trigger = make_trigger(entity_id="truck-002", event_type="new_order")

    world_slice = make_world_slice(
        entity={
            "id": "truck-002",
            "truck_type": "proprietario",
            "degradation": 0.5,
            "cargo": {},
            "status": "idle",
        }
    )

    llm_response = AIMessage(content='{"action": "accept_contract", "payload": {}}')
    fake_chat = FakeListChatModel(responses=[llm_response])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                    with patch("src.agents.truck_agent.TruckDecision", stub_schema):
                        await agent.run_cycle(trigger)

    # LLM was reached: decision was persisted
    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["entity_id"] == "truck-002"
