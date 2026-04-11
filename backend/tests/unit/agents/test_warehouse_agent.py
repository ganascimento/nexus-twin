from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage

from src.agents.warehouse_agent import WarehouseAgent
from src.simulation.events import SimulationEvent


def make_trigger(entity_id: str = "warehouse-001", event_type: str = "order_received") -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type="warehouse",
        entity_id=entity_id,
        payload={},
        tick=1,
    )


def make_world_slice(entity: dict | None = None) -> dict:
    return {
        "entity": entity or {
            "id": "warehouse-001",
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
    agent = WarehouseAgent("warehouse-001", mock_db_session, mock_publisher)
    trigger = make_trigger()
    world_slice = make_world_slice()

    llm_response = AIMessage(content='{"action": "confirm_order", "payload": {}}')
    fake_chat = FakeListChatModel(responses=[llm_response])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                    with patch("src.agents.warehouse_agent.WarehouseDecision", stub_schema):
                        await agent.run_cycle(trigger)

    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["agent_type"] == "warehouse"
    assert call_data["entity_id"] == "warehouse-001"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_warehouse_stocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_warehouse_stocks(mock_db_session, mock_publisher):
    agent = WarehouseAgent("warehouse-001", mock_db_session, mock_publisher)

    mock_stock = MagicMock()
    mock_stock.material_id = "tijolos"
    mock_stock.stock = 80.0

    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-001"
    mock_warehouse.name = "Armazém Jundiaí"
    mock_warehouse.stocks = [mock_stock]

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.get_by_id.return_value = mock_warehouse

    mock_factory_repo = AsyncMock()
    mock_factory_repo.list_partner_for_warehouse.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = []

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.warehouse_agent.WarehouseRepository", return_value=mock_warehouse_repo):
        with patch("src.agents.warehouse_agent.FactoryRepository", return_value=mock_factory_repo):
            with patch("src.agents.warehouse_agent.OrderRepository", return_value=mock_order_repo):
                with patch("src.agents.warehouse_agent.EventRepository", return_value=mock_event_repo):
                    world_slice = await agent._build_world_state_slice(current_tick=1)

    entity = world_slice["entity"]
    assert "stocks" in entity or "warehouse_stocks" in entity


# ---------------------------------------------------------------------------
# test_build_world_state_slice_limits_related_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_limits_related_entities(mock_db_session, mock_publisher):
    agent = WarehouseAgent("warehouse-001", mock_db_session, mock_publisher)

    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-001"
    mock_warehouse.stocks = []

    fifteen_factories = [MagicMock(id=f"factory-{i:03d}") for i in range(15)]

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.get_by_id.return_value = mock_warehouse

    mock_factory_repo = AsyncMock()
    mock_factory_repo.list_partner_for_warehouse.return_value = fifteen_factories

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = []

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.warehouse_agent.WarehouseRepository", return_value=mock_warehouse_repo):
        with patch("src.agents.warehouse_agent.FactoryRepository", return_value=mock_factory_repo):
            with patch("src.agents.warehouse_agent.OrderRepository", return_value=mock_order_repo):
                with patch("src.agents.warehouse_agent.EventRepository", return_value=mock_event_repo):
                    world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["related_entities"]) <= 10


# ---------------------------------------------------------------------------
# test_build_world_state_slice_filters_pending_orders_by_target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_filters_pending_orders_by_target(mock_db_session, mock_publisher):
    agent = WarehouseAgent("warehouse-001", mock_db_session, mock_publisher)

    mock_warehouse = MagicMock()
    mock_warehouse.id = "warehouse-001"
    mock_warehouse.stocks = []

    order_for_target = MagicMock()
    order_for_target.target_id = "warehouse-001"

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.get_by_id.return_value = mock_warehouse

    mock_factory_repo = AsyncMock()
    mock_factory_repo.list_partner_for_warehouse.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_target.return_value = [order_for_target]

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.warehouse_agent.WarehouseRepository", return_value=mock_warehouse_repo):
        with patch("src.agents.warehouse_agent.FactoryRepository", return_value=mock_factory_repo):
            with patch("src.agents.warehouse_agent.OrderRepository", return_value=mock_order_repo):
                with patch("src.agents.warehouse_agent.EventRepository", return_value=mock_event_repo):
                    world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["pending_orders"]) == 1
    mock_order_repo.get_pending_for_target.assert_called_once_with("warehouse-001")
