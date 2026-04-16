from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.enums import FactoryStatus, WarehouseStatus
from src.simulation.engine import SimulationEngine
from src.world.entities.factory import Factory, FactoryProduct
from src.world.entities.warehouse import Warehouse, WarehouseStock
from src.world.state import WorldState


def make_world_state(**kwargs):
    defaults = dict(
        tick=1,
        simulated_timestamp=datetime(2024, 1, 1),
        materials=[],
        factories=[],
        warehouses=[],
        stores=[],
        trucks=[],
    )
    defaults.update(kwargs)
    return WorldState(**defaults)


def make_warehouse(stocks=None, **kwargs):
    defaults = dict(
        id="wh_01",
        name="Warehouse 1",
        lat=-22.8,
        lng=-45.8,
        region="interior",
        capacity_total=1000.0,
        status=WarehouseStatus.OPERATING,
        stocks=stocks or {},
    )
    defaults.update(kwargs)
    return Warehouse(**defaults)


def make_factory(products=None, **kwargs):
    defaults = dict(
        id="factory_01",
        name="Factory 1",
        lat=-22.9,
        lng=-47.1,
        status=FactoryStatus.OPERATING,
        products=products or {},
        partner_warehouses=[],
    )
    defaults.update(kwargs)
    return Factory(**defaults)


def make_pending_order(
    id=None,
    target_id="wh_01",
    material_id="cimento",
    quantity_tons=20,
    requester_type="store",
    requester_id="store_01",
    status="pending",
    triggered_at_tick=None,
):
    order = MagicMock()
    order.id = id or uuid4()
    order.target_id = target_id
    order.material_id = material_id
    order.quantity_tons = quantity_tons
    order.requester_type = requester_type
    order.requester_id = requester_id
    order.status = status
    order.triggered_at_tick = triggered_at_tick
    return order


def make_engine():
    redis_client = AsyncMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    engine = SimulationEngine(redis_client, session_factory)
    return engine, mock_session


# ---------------------------------------------------------------------------
# Order-based triggers for warehouses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_triggers_fires_order_received_for_warehouse():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    pending_order = make_pending_order(target_id="wh_01")

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [pending_order]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    order_triggers = [
        t for t in triggers if t[1].event_type == "order_received"
    ]
    assert len(order_triggers) == 1
    assert order_triggers[0][1].entity_id == "wh_01"
    assert order_triggers[0][1].entity_type == "warehouse"


@pytest.mark.asyncio
async def test_evaluate_triggers_fires_resupply_requested_for_factory():
    factory = make_factory(
        products={
            "cimento": FactoryProduct(
                stock=100.0, stock_reserved=0.0, stock_max=200.0,
                production_rate_max=10.0, production_rate_current=5.0,
            )
        }
    )
    world_state = make_world_state(factories=[factory])

    pending_order = make_pending_order(
        target_id="factory_01",
        requester_type="warehouse",
        requester_id="wh_01",
    )

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [pending_order]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    resupply_triggers = [
        t for t in triggers if t[1].event_type == "resupply_requested"
    ]
    assert len(resupply_triggers) == 1
    assert resupply_triggers[0][1].entity_id == "factory_01"
    assert resupply_triggers[0][1].entity_type == "factory"


@pytest.mark.asyncio
async def test_evaluate_triggers_marks_order_as_triggered():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    pending_order = make_pending_order(target_id="wh_01")
    order_id = pending_order.id

    engine, _ = make_engine()
    engine._tick = 7

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [pending_order]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        await engine._evaluate_triggers(world_state)

    mock_order_repo.mark_triggered.assert_called_once_with(order_id, 7)


@pytest.mark.asyncio
async def test_evaluate_triggers_skips_already_triggered_orders():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    order_triggers = [
        t for t in triggers if t[1].event_type == "order_received"
    ]
    assert len(order_triggers) == 0


@pytest.mark.asyncio
async def test_evaluate_triggers_warehouse_both_stock_and_order_triggers():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=55.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    pending_order = make_pending_order(target_id="wh_01")

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [pending_order]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    wh_triggers = [t for t in triggers if t[1].entity_id == "wh_01"]
    event_types = {t[1].event_type for t in wh_triggers}
    assert "stock_trigger_warehouse" in event_types
    assert "order_received" in event_types
    assert len(wh_triggers) >= 2


@pytest.mark.asyncio
async def test_evaluate_triggers_multiple_orders_for_same_target():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    order_1 = make_pending_order(target_id="wh_01", material_id="cimento")
    order_2 = make_pending_order(target_id="wh_01", material_id="vergalhao")

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [order_1, order_2]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    order_triggers = [
        t for t in triggers if t[1].event_type == "order_received"
    ]
    assert len(order_triggers) == 2
    assert mock_order_repo.mark_triggered.call_count == 2


@pytest.mark.asyncio
async def test_evaluate_triggers_order_payload_contains_order_data():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    world_state = make_world_state(warehouses=[warehouse])

    order_id = uuid4()
    pending_order = make_pending_order(
        id=order_id,
        target_id="wh_01",
        material_id="cimento",
        quantity_tons=30,
        requester_type="store",
        requester_id="store_01",
    )

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = [pending_order]
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    order_trigger = [
        t for t in triggers if t[1].event_type == "order_received"
    ][0]
    payload = order_trigger[1].payload
    assert payload["order_id"] == str(order_id)
    assert payload["requester_type"] == "store"
    assert payload["requester_id"] == "store_01"
    assert payload["material_id"] == "cimento"
    assert payload["quantity_tons"] == 30


@pytest.mark.asyncio
async def test_evaluate_triggers_no_pending_orders_no_extra_triggers():
    warehouse = make_warehouse(
        stocks={"cimento": WarehouseStock(stock=500.0, stock_reserved=0.0, min_stock=50.0)}
    )
    factory = make_factory(
        products={
            "cimento": FactoryProduct(
                stock=100.0, stock_reserved=0.0, stock_max=200.0,
                production_rate_max=10.0, production_rate_current=5.0,
            )
        }
    )
    world_state = make_world_state(warehouses=[warehouse], factories=[factory])

    engine, _ = make_engine()
    engine._tick = 5

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = []

        triggers = await engine._evaluate_triggers(world_state)

    order_triggers = [
        t for t in triggers
        if t[1].event_type in ("order_received", "resupply_requested")
    ]
    assert len(order_triggers) == 0


# ---------------------------------------------------------------------------
# Re-trigger for fulfillable factory orders (anti-deadlock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_triggers_resets_triggered_for_fulfillable_factory_order():
    factory = make_factory(
        products={
            "cimento": FactoryProduct(
                stock=100.0, stock_reserved=0.0, stock_max=200.0,
                production_rate_max=10.0, production_rate_current=5.0,
            )
        }
    )
    world_state = make_world_state(factories=[factory])

    triggered_order = make_pending_order(
        target_id="factory_01",
        material_id="cimento",
        quantity_tons=50,
        triggered_at_tick=5,
        status="pending",
    )
    order_id = triggered_order.id

    engine, _ = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = [triggered_order]

        await engine._evaluate_triggers(world_state)

    mock_order_repo.reset_triggered.assert_called_once_with(order_id)


@pytest.mark.asyncio
async def test_evaluate_triggers_does_not_reset_if_insufficient_stock():
    factory = make_factory(
        products={
            "cimento": FactoryProduct(
                stock=10.0, stock_reserved=0.0, stock_max=200.0,
                production_rate_max=10.0, production_rate_current=5.0,
            )
        }
    )
    world_state = make_world_state(factories=[factory])

    triggered_order = make_pending_order(
        target_id="factory_01",
        material_id="cimento",
        quantity_tons=50,
        triggered_at_tick=5,
        status="pending",
    )

    engine, _ = make_engine()
    engine._tick = 10

    with patch("src.simulation.engine.EventRepository") as MockEventRepo, \
         patch("src.simulation.engine.OrderRepository") as MockOrderRepo:
        mock_event_repo = AsyncMock()
        MockEventRepo.return_value = mock_event_repo
        mock_event_repo.get_active_for_entity.return_value = []

        mock_order_repo = AsyncMock()
        MockOrderRepo.return_value = mock_order_repo
        mock_order_repo.get_untriggered_for_target.return_value = []
        mock_order_repo.get_triggered_but_pending_for_target.return_value = [triggered_order]

        await engine._evaluate_triggers(world_state)

    mock_order_repo.reset_triggered.assert_not_called()
