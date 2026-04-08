from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage

from src.agents.factory_agent import FactoryAgent
from src.simulation.events import SimulationEvent


def make_trigger(entity_id: str = "factory-001", event_type: str = "stock_projection") -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type="factory",
        entity_id=entity_id,
        payload={},
        tick=1,
    )


def make_world_slice(entity: dict | None = None) -> dict:
    return {
        "entity": entity or {
            "id": "factory-001",
            "stock": {"tijolos": 50.0},
            "stock_max": {"tijolos": 100.0},
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
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)
    trigger = make_trigger()
    world_slice = make_world_slice()

    llm_response = AIMessage(content='{"action": "start_production", "payload": {}}')
    fake_chat = FakeListChatModel(responses=[llm_response])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("src.agents.base.AsyncSession", MagicMock()):
                    with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                        with patch("src.agents.factory_agent.FactoryDecision", stub_schema):
                            await agent.run_cycle(trigger)

    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["action"] == "start_production"
    assert call_data["entity_id"] == "factory-001"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_factory_products
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_factory_products(mock_db_session, mock_publisher):
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)

    mock_product = MagicMock()
    mock_product.material_id = "tijolos"
    mock_product.stock = 10.0

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.name = "Fábrica Campinas"
    mock_factory.products = [mock_product]

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = []

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = []

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        with patch("src.agents.factory_agent.EventRepository", return_value=mock_event_repo):
            with patch("src.agents.factory_agent.OrderRepository", return_value=mock_order_repo):
                world_slice = await agent._build_world_state_slice(current_tick=1)

    entity = world_slice["entity"]
    assert "products" in entity or "factory_products" in entity


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_partner_warehouses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_partner_warehouses(mock_db_session, mock_publisher):
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.products = []

    mock_warehouse_1 = MagicMock()
    mock_warehouse_1.id = "warehouse-001"
    mock_warehouse_2 = MagicMock()
    mock_warehouse_2.id = "warehouse-002"

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = [mock_warehouse_1, mock_warehouse_2]

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = []

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        with patch("src.agents.factory_agent.EventRepository", return_value=mock_event_repo):
            with patch("src.agents.factory_agent.OrderRepository", return_value=mock_order_repo):
                world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["related_entities"]) == 2


# ---------------------------------------------------------------------------
# test_build_world_state_slice_filters_active_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_filters_active_events(mock_db_session, mock_publisher):
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.products = []

    event_for_entity = MagicMock()
    event_for_entity.entity_id = "factory-001"

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = []

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = [event_for_entity]

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = []

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        with patch("src.agents.factory_agent.EventRepository", return_value=mock_event_repo):
            with patch("src.agents.factory_agent.OrderRepository", return_value=mock_order_repo):
                world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["active_events"]) == 1
    mock_event_repo.get_active_for_entity.assert_called_once_with("factory", "factory-001")
