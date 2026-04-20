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
    mock_product.stock_reserved = 0.0
    mock_product.stock_max = 100.0
    mock_product.production_rate_current = 0.0
    mock_product.production_rate_max = 10.0

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.status = "operating"
    mock_factory.products = [mock_product]

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = []

    trigger = MagicMock()
    trigger.event_type = "stock_trigger_factory"
    trigger.payload = {}

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        world_slice = await agent._build_world_state_slice(trigger)

    entity = world_slice["entity"]
    assert len(entity["products"]) == 1
    assert entity["products"][0]["material_id"] == "tijolos"


# ---------------------------------------------------------------------------
# test_build_world_state_slice_includes_partner_warehouses_only_on_stock_or_resupply
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_includes_partner_warehouses(mock_db_session, mock_publisher):
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.status = "operating"
    mock_factory.products = []

    mock_warehouse_1 = MagicMock(id="warehouse-001", name="w1", lat=0, lng=0, region="a", capacity_total=500, status="operating")
    mock_warehouse_2 = MagicMock(id="warehouse-002", name="w2", lat=0, lng=0, region="b", capacity_total=500, status="operating")

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = [mock_warehouse_1, mock_warehouse_2]

    trigger = MagicMock()
    trigger.event_type = "stock_trigger_factory"
    trigger.payload = {}

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        world_slice = await agent._build_world_state_slice(trigger)

    assert len(world_slice["related_entities"]) == 2


# ---------------------------------------------------------------------------
# test_build_world_state_slice_filters_products_to_requested_material
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_world_state_slice_filters_products_by_material_on_resupply_requested(mock_db_session, mock_publisher):
    agent = FactoryAgent("factory-001", mock_db_session, mock_publisher)

    product_tijolos = MagicMock(material_id="tijolos", stock=10.0, stock_reserved=0.0,
                                 stock_max=100.0, production_rate_current=0.0, production_rate_max=10.0)
    product_cimento = MagicMock(material_id="cimento", stock=50.0, stock_reserved=0.0,
                                 stock_max=100.0, production_rate_current=0.0, production_rate_max=10.0)

    mock_factory = MagicMock()
    mock_factory.id = "factory-001"
    mock_factory.status = "operating"
    mock_factory.products = [product_tijolos, product_cimento]

    mock_factory_repo = AsyncMock()
    mock_factory_repo.get_by_id.return_value = mock_factory
    mock_factory_repo.get_partner_warehouses.return_value = []

    trigger = MagicMock()
    trigger.event_type = "resupply_requested"
    trigger.payload = {"material_id": "cimento"}

    with patch("src.agents.factory_agent.FactoryRepository", return_value=mock_factory_repo):
        world_slice = await agent._build_world_state_slice(trigger)

    products = world_slice["entity"]["products"]
    assert len(products) == 1
    assert products[0]["material_id"] == "cimento"
