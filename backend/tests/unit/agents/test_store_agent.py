from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage

from src.agents.store_agent import StoreAgent
from src.simulation.events import SimulationEvent


def make_trigger(entity_id: str = "store-001", event_type: str = "stock_projection") -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type="store",
        entity_id=entity_id,
        payload={},
        tick=1,
    )


def make_world_slice(entity: dict | None = None) -> dict:
    return {
        "entity": entity or {
            "id": "store-001",
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
    agent = StoreAgent("store-001", mock_db_session, mock_publisher)
    trigger = make_trigger()
    world_slice = make_world_slice()

    llm_response = AIMessage(content='{"action": "order_replenishment", "payload": {}}')
    fake_chat = FakeListChatModel(responses=[llm_response])

    mock_repo = AsyncMock()
    mock_repo.get_recent_by_entity.return_value = []
    stub_schema = MagicMock(return_value=MagicMock())

    with patch.object(agent, "_build_world_state_slice", AsyncMock(return_value=world_slice)):
        with patch("src.agents.base.ChatOpenAI", return_value=fake_chat):
            with patch("src.agents.base.AgentDecisionRepository", return_value=mock_repo):
                with patch("src.agents.base.AsyncSession", MagicMock()):
                    with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                        with patch("src.agents.store_agent.StoreDecision", stub_schema):
                            await agent.run_cycle(trigger)

    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["entity_type"] == "store"
    assert call_data["entity_id"] == "store-001"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_store_stocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_store_stocks(mock_db_session, mock_publisher):
    agent = StoreAgent("store-001", mock_db_session, mock_publisher)

    mock_stock = MagicMock()
    mock_stock.material_id = "tijolos"
    mock_stock.stock = 20.0
    mock_stock.demand_rate = 5.0
    mock_stock.reorder_point = 15.0

    mock_store = MagicMock()
    mock_store.id = "store-001"
    mock_store.name = "Loja SP Capital"
    mock_store.region = "SP"
    mock_store.stocks = [mock_stock]

    mock_store_repo = AsyncMock()
    mock_store_repo.get_by_id.return_value = mock_store

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.list_by_region.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_requester.return_value = []

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.store_agent.StoreRepository", return_value=mock_store_repo):
        with patch("src.agents.store_agent.WarehouseRepository", return_value=mock_warehouse_repo):
            with patch("src.agents.store_agent.OrderRepository", return_value=mock_order_repo):
                with patch("src.agents.store_agent.EventRepository", return_value=mock_event_repo):
                    world_slice = await agent._build_world_state_slice(current_tick=1)

    entity = world_slice["entity"]
    assert "stocks" in entity or "store_stocks" in entity


# ---------------------------------------------------------------------------
# test_build_world_state_slice_filters_pending_orders_by_requester
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_filters_pending_orders_by_requester(mock_db_session, mock_publisher):
    agent = StoreAgent("store-001", mock_db_session, mock_publisher)

    mock_store = MagicMock()
    mock_store.id = "store-001"
    mock_store.region = "SP"
    mock_store.stocks = []

    order_by_requester = MagicMock()
    order_by_requester.requester_id = "store-001"

    mock_store_repo = AsyncMock()
    mock_store_repo.get_by_id.return_value = mock_store

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.list_by_region.return_value = []

    mock_order_repo = AsyncMock()
    mock_order_repo.get_pending_for_requester.return_value = [order_by_requester]

    mock_event_repo = AsyncMock()
    mock_event_repo.get_active_for_entity.return_value = []

    with patch("src.agents.store_agent.StoreRepository", return_value=mock_store_repo):
        with patch("src.agents.store_agent.WarehouseRepository", return_value=mock_warehouse_repo):
            with patch("src.agents.store_agent.OrderRepository", return_value=mock_order_repo):
                with patch("src.agents.store_agent.EventRepository", return_value=mock_event_repo):
                    world_slice = await agent._build_world_state_slice(current_tick=1)

    assert len(world_slice["pending_orders"]) == 1
    mock_order_repo.get_pending_for_requester.assert_called_once_with("store-001")
