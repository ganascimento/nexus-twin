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
                with patch("pathlib.Path.read_text", return_value="You are {entity_id}"):
                    with patch("src.agents.store_agent.StoreDecision", stub_schema):
                        await agent.run_cycle(trigger)

    mock_repo.create.assert_called_once()
    call_data = mock_repo.create.call_args[0][0]
    assert call_data["agent_type"] == "store"
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
    mock_store.lat = -23.5
    mock_store.lng = -46.6
    mock_store.stocks = [mock_stock]

    mock_store_repo = AsyncMock()
    mock_store_repo.get_by_id.return_value = mock_store

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.get_all.return_value = []

    trigger = MagicMock()
    trigger.event_type = "low_stock_trigger"
    trigger.payload = {}

    with patch("src.agents.store_agent.StoreRepository", return_value=mock_store_repo):
        with patch("src.agents.store_agent.WarehouseRepository", return_value=mock_warehouse_repo):
            world_slice = await agent._build_world_state_slice(trigger)

    entity = world_slice["entity"]
    assert entity["stocks"][0]["material_id"] == "tijolos"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_filters_warehouses_by_material
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_filters_warehouses_by_material(mock_db_session, mock_publisher):
    agent = StoreAgent("store-001", mock_db_session, mock_publisher)

    mock_store = MagicMock()
    mock_store.id = "store-001"
    mock_store.lat = -23.5
    mock_store.lng = -46.6
    mock_store.stocks = []

    wh_with_mat = MagicMock()
    wh_with_mat.id = "wh-1"
    wh_with_mat.region = "a"
    wh_with_mat.lat = 0
    wh_with_mat.lng = 0
    s_cimento = MagicMock(material_id="cimento", stock=100.0, stock_reserved=0.0)
    wh_with_mat.stocks = [s_cimento]

    wh_without_mat = MagicMock()
    wh_without_mat.id = "wh-2"
    wh_without_mat.region = "b"
    wh_without_mat.lat = 0
    wh_without_mat.lng = 0
    s_other = MagicMock(material_id="tijolos", stock=50.0, stock_reserved=0.0)
    wh_without_mat.stocks = [s_other]

    mock_store_repo = AsyncMock()
    mock_store_repo.get_by_id.return_value = mock_store

    mock_warehouse_repo = AsyncMock()
    mock_warehouse_repo.get_all.return_value = [wh_with_mat, wh_without_mat]

    trigger = MagicMock()
    trigger.event_type = "low_stock_trigger"
    trigger.payload = {"material_id": "cimento"}

    with patch("src.agents.store_agent.StoreRepository", return_value=mock_store_repo):
        with patch("src.agents.store_agent.WarehouseRepository", return_value=mock_warehouse_repo):
            world_slice = await agent._build_world_state_slice(trigger)

    related = world_slice["related_entities"]
    assert len(related) == 1
    assert related[0]["id"] == "wh-1"
