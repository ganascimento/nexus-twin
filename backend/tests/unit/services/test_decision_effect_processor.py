from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from src.services.decision_effect_processor import DecisionEffectProcessor


def _make_mock_order(
    id=None,
    requester_type="store",
    requester_id="store_01",
    target_type="warehouse",
    target_id="wh_01",
    material_id="cimento",
    quantity_tons=20,
    status="pending",
):
    order = MagicMock()
    order.id = id or uuid4()
    order.requester_type = requester_type
    order.requester_id = requester_id
    order.target_type = target_type
    order.target_id = target_id
    order.material_id = material_id
    order.quantity_tons = quantity_tons
    order.status = status
    return order


def _make_mock_truck(
    id="truck_01",
    truck_type="terceiro",
    status="idle",
    current_lat=-23.55,
    current_lng=-46.63,
    factory_id=None,
    capacity_tons=30.0,
    degradation=0.2,
):
    truck = MagicMock()
    truck.id = id
    truck.truck_type = truck_type
    truck.status = status
    truck.current_lat = current_lat
    truck.current_lng = current_lng
    truck.factory_id = factory_id
    truck.capacity_tons = capacity_tons
    truck.degradation = degradation
    return truck


def _make_mock_warehouse(id="wh_01", lat=-23.0, lng=-46.0):
    wh = MagicMock()
    wh.id = id
    wh.lat = lat
    wh.lng = lng
    return wh


def _make_mock_store(id="store_01", lat=-23.5, lng=-46.6):
    store = MagicMock()
    store.id = id
    store.lat = lat
    store.lng = lng
    return store


def _make_mock_factory(id="factory_01", lat=-22.9, lng=-47.0):
    factory = MagicMock()
    factory.id = id
    factory.lat = lat
    factory.lng = lng
    return factory


@pytest.fixture
def mock_order_repo():
    repo = AsyncMock()
    repo.has_active_order = AsyncMock(return_value=False)
    repo.create = AsyncMock(return_value=_make_mock_order())
    repo.get_by_id = AsyncMock(return_value=_make_mock_order())
    return repo


@pytest.fixture
def mock_warehouse_service():
    svc = AsyncMock()
    svc.confirm_order = AsyncMock()
    svc.reject_order = AsyncMock()
    return svc


@pytest.fixture
def mock_factory_repo():
    repo = AsyncMock()
    repo.update_production_rate = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=_make_mock_factory())
    return repo


@pytest.fixture
def mock_truck_service():
    svc = AsyncMock()
    svc.assign_route = AsyncMock()
    svc.schedule_maintenance = AsyncMock()
    return svc


@pytest.fixture
def mock_route_service():
    svc = AsyncMock()
    route_data = {
        "path": [[-46.63, -23.55], [-46.0, -23.0]],
        "timestamps": [5, 8],
        "distance_km": 100,
        "eta_ticks": 3,
    }
    svc.compute_route = AsyncMock(return_value=route_data)
    created_route = MagicMock()
    created_route.id = uuid4()
    svc.create_route = AsyncMock(return_value=created_route)
    return svc


@pytest.fixture
def mock_event_repo():
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=MagicMock(id=uuid4()))
    return repo


@pytest.fixture
def mock_truck_repo():
    repo = AsyncMock()
    idle_truck = _make_mock_truck()
    repo.get_all = AsyncMock(return_value=[idle_truck])
    repo.get_by_id = AsyncMock(return_value=idle_truck)
    repo.get_by_factory = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_warehouse_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=_make_mock_warehouse())
    return repo


@pytest.fixture
def mock_store_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=_make_mock_store())
    return repo


@pytest.fixture
def processor(
    mock_order_repo,
    mock_warehouse_service,
    mock_factory_repo,
    mock_truck_service,
    mock_route_service,
    mock_event_repo,
    mock_truck_repo,
    mock_warehouse_repo,
    mock_store_repo,
):
    return DecisionEffectProcessor(
        order_repo=mock_order_repo,
        warehouse_service=mock_warehouse_service,
        factory_repo=mock_factory_repo,
        truck_service=mock_truck_service,
        route_service=mock_route_service,
        event_repo=mock_event_repo,
        truck_repo=mock_truck_repo,
        warehouse_repo=mock_warehouse_repo,
        store_repo=mock_store_repo,
        route_repo=AsyncMock(),
    )


# --- Test: hold is no-op ---


@pytest.mark.asyncio
async def test_process_hold_is_noop(
    processor,
    mock_order_repo,
    mock_warehouse_service,
    mock_factory_repo,
    mock_truck_service,
    mock_route_service,
    mock_event_repo,
):
    await processor.process("store", "store_01", "hold", {}, current_tick=5)

    mock_order_repo.create.assert_not_called()
    mock_order_repo.has_active_order.assert_not_called()
    mock_warehouse_service.confirm_order.assert_not_called()
    mock_warehouse_service.reject_order.assert_not_called()
    mock_factory_repo.update_production_rate.assert_not_called()
    mock_truck_service.assign_route.assert_not_called()
    mock_truck_service.schedule_maintenance.assert_not_called()
    mock_route_service.compute_route.assert_not_called()
    mock_event_repo.create.assert_not_called()


# --- Test: unknown action ---


@pytest.mark.asyncio
async def test_process_unknown_action_logs_warning(
    processor,
    mock_order_repo,
    mock_warehouse_service,
    mock_truck_service,
):
    await processor.process("store", "store_01", "unknown_action", {}, current_tick=5)

    mock_order_repo.create.assert_not_called()
    mock_warehouse_service.confirm_order.assert_not_called()
    mock_truck_service.assign_route.assert_not_called()


# --- Tests: order_replenishment (StoreAgent) ---


@pytest.mark.asyncio
async def test_order_replenishment_creates_pending_order(processor, mock_order_repo):
    payload = {
        "material_id": "cimento",
        "quantity_tons": 20,
        "from_warehouse_id": "wh_01",
    }

    await processor.process(
        "store", "store_01", "order_replenishment", payload, current_tick=5
    )

    mock_order_repo.has_active_order.assert_called_once_with(
        "store_01", "cimento", "wh_01"
    )
    mock_order_repo.create.assert_called_once()
    call_args = mock_order_repo.create.call_args
    created = (
        call_args[0][0] if call_args[0] else call_args[1].get("data", call_args[0][0])
    )
    assert created["requester_type"] == "store"
    assert created["requester_id"] == "store_01"
    assert created["target_type"] == "warehouse"
    assert created["target_id"] == "wh_01"
    assert created["material_id"] == "cimento"
    assert created["quantity_tons"] == 20
    assert created["status"] == "pending"


@pytest.mark.asyncio
async def test_order_replenishment_deduplicates(processor, mock_order_repo):
    mock_order_repo.has_active_order.return_value = True

    payload = {
        "material_id": "cimento",
        "quantity_tons": 20,
        "from_warehouse_id": "wh_01",
    }

    await processor.process(
        "store", "store_01", "order_replenishment", payload, current_tick=5
    )

    mock_order_repo.has_active_order.assert_called_once()
    mock_order_repo.create.assert_not_called()


# --- Tests: confirm_order (WarehouseAgent) ---


@pytest.mark.asyncio
async def test_confirm_order_calls_warehouse_service(
    processor,
    mock_warehouse_service,
    mock_event_repo,
    mock_truck_repo,
    mock_order_repo,
):
    order = _make_mock_order(
        requester_type="store",
        requester_id="store_01",
        target_type="warehouse",
        target_id="wh_01",
    )
    mock_order_repo.get_by_id.return_value = order

    payload = {"order_id": "order_007", "quantity_tons": 50, "eta_ticks": 3}

    await processor.process(
        "warehouse", "wh_01", "confirm_order", payload, current_tick=5
    )

    mock_warehouse_service.confirm_order.assert_called_once_with("order_007", 3)
    mock_event_repo.create.assert_called_once()
    event_data = mock_event_repo.create.call_args[0][0]
    assert event_data["event_type"] == "contract_proposal"
    assert event_data["entity_type"] == "truck"
    assert event_data["status"] == "active"


@pytest.mark.asyncio
async def test_confirm_order_no_truck_available(
    processor,
    mock_warehouse_service,
    mock_event_repo,
    mock_truck_repo,
    mock_order_repo,
):
    order = _make_mock_order(
        requester_type="store",
        requester_id="store_01",
        target_type="warehouse",
        target_id="wh_01",
    )
    mock_order_repo.get_by_id.return_value = order
    mock_truck_repo.get_all.return_value = []

    payload = {"order_id": "order_007", "quantity_tons": 50, "eta_ticks": 3}

    await processor.process(
        "warehouse", "wh_01", "confirm_order", payload, current_tick=5
    )

    mock_warehouse_service.confirm_order.assert_called_once_with("order_007", 3)
    mock_event_repo.create.assert_not_called()


# --- Tests: reject_order (WarehouseAgent) ---


@pytest.mark.asyncio
async def test_reject_order_calls_warehouse_service(processor, mock_warehouse_service):
    payload = {
        "order_id": "order_007",
        "reason": "insuficiente",
        "retry_after_ticks": 5,
    }

    await processor.process(
        "warehouse", "wh_01", "reject_order", payload, current_tick=5
    )

    mock_warehouse_service.reject_order.assert_called_once_with(
        "order_007", "insuficiente", retry_after_ticks=5
    )


# --- Tests: request_resupply (WarehouseAgent) ---


@pytest.mark.asyncio
async def test_request_resupply_creates_order_to_factory(processor, mock_order_repo):
    payload = {
        "material_id": "cimento",
        "quantity_tons": 80,
        "from_factory_id": "factory_01",
    }

    await processor.process(
        "warehouse", "wh_01", "request_resupply", payload, current_tick=5
    )

    mock_order_repo.has_active_order.assert_called_once_with(
        "wh_01", "cimento", "factory_01"
    )
    mock_order_repo.create.assert_called_once()
    created = mock_order_repo.create.call_args[0][0]
    assert created["requester_type"] == "warehouse"
    assert created["requester_id"] == "wh_01"
    assert created["target_type"] == "factory"
    assert created["target_id"] == "factory_01"
    assert created["material_id"] == "cimento"
    assert created["quantity_tons"] == 80
    assert created["status"] == "pending"


@pytest.mark.asyncio
async def test_request_resupply_deduplicates(processor, mock_order_repo):
    mock_order_repo.has_active_order.return_value = True

    payload = {
        "material_id": "cimento",
        "quantity_tons": 80,
        "from_factory_id": "factory_01",
    }

    await processor.process(
        "warehouse", "wh_01", "request_resupply", payload, current_tick=5
    )

    mock_order_repo.has_active_order.assert_called_once()
    mock_order_repo.create.assert_not_called()


# --- Tests: start_production (FactoryAgent) ---


@pytest.mark.asyncio
async def test_start_production_updates_factory(processor, mock_factory_repo):
    payload = {"material_id": "cimento", "quantity_tons": 100}

    await processor.process(
        "factory", "factory_01", "start_production", payload, current_tick=5
    )

    mock_factory_repo.update_production_rate.assert_called_once_with(
        "factory_01", "cimento", 100
    )


# --- Tests: send_stock (FactoryAgent) ---


@pytest.mark.asyncio
async def test_send_stock_creates_order_and_event(
    processor,
    mock_order_repo,
    mock_event_repo,
    mock_truck_repo,
    mock_factory_repo,
):
    proprietario_truck = _make_mock_truck(
        id="truck_prop_01",
        truck_type="proprietario",
        status="idle",
        factory_id="factory_01",
    )
    mock_truck_repo.get_by_factory.return_value = [proprietario_truck]
    mock_order_repo.get_active_by_requester_target_material.return_value = None
    mock_factory_repo.atomic_reserve_stock.return_value = True

    payload = {
        "material_id": "cimento",
        "quantity_tons": 50,
        "destination_warehouse_id": "wh_01",
    }

    await processor.process(
        "factory", "factory_01", "send_stock", payload, current_tick=5
    )

    mock_factory_repo.atomic_reserve_stock.assert_called_once_with(
        "factory_01", "cimento", 50
    )
    mock_order_repo.create.assert_called_once()
    created = mock_order_repo.create.call_args[0][0]
    assert created["requester_type"] == "warehouse"
    assert created["requester_id"] == "wh_01"
    assert created["target_type"] == "factory"
    assert created["target_id"] == "factory_01"
    assert created["status"] == "confirmed"

    mock_event_repo.create.assert_called_once()
    event_data = mock_event_repo.create.call_args[0][0]
    assert event_data["event_type"] == "new_order"
    assert event_data["entity_type"] == "truck"
    assert event_data["entity_id"] == "truck_prop_01"


# --- Tests: accept_contract (TruckAgent) ---


@pytest.mark.asyncio
async def test_accept_contract_assigns_route(
    processor,
    mock_truck_repo,
    mock_order_repo,
    mock_route_service,
    mock_truck_service,
    mock_warehouse_repo,
    mock_store_repo,
):
    truck = _make_mock_truck(id="truck_01", current_lat=-23.55, current_lng=-46.63)
    mock_truck_repo.get_by_id.return_value = truck

    order = _make_mock_order(
        id="order_007",
        requester_type="store",
        requester_id="store_01",
        target_type="warehouse",
        target_id="wh_01",
    )
    mock_order_repo.get_by_id.return_value = order

    warehouse = _make_mock_warehouse(id="wh_01", lat=-23.0, lng=-46.0)
    mock_warehouse_repo.get_by_id.return_value = warehouse

    store = _make_mock_store(id="store_01", lat=-23.5, lng=-46.6)
    mock_store_repo.get_by_id.return_value = store

    payload = {"order_id": "order_007", "chosen_route_risk_level": "low"}

    await processor.process(
        "truck", "truck_01", "accept_contract", payload, current_tick=5
    )

    mock_route_service.compute_route.assert_called_once()
    mock_route_service.create_route.assert_called_once()
    mock_truck_service.assign_route.assert_called_once()

    assign_args = mock_truck_service.assign_route.call_args
    assert assign_args[0][0] == "truck_01"


# --- Tests: request_maintenance (TruckAgent) ---


@pytest.mark.asyncio
async def test_request_maintenance_schedules(processor, mock_truck_service):
    payload = {"current_degradation": 0.96}

    await processor.process(
        "truck", "truck_01", "request_maintenance", payload, current_tick=5
    )

    mock_truck_service.schedule_maintenance.assert_called_once_with("truck_01", current_tick=5)


# --- Tests: refuse_contract (TruckAgent) ---


@pytest.mark.asyncio
async def test_refuse_contract_publishes_event(
    processor,
    mock_event_repo,
    mock_truck_repo,
    mock_order_repo,
):
    order = _make_mock_order(
        id="order_007",
        requester_type="store",
        requester_id="store_01",
        target_type="warehouse",
        target_id="wh_01",
    )
    mock_order_repo.get_by_id.return_value = order

    next_truck = _make_mock_truck(id="truck_02", status="idle")
    mock_truck_repo.get_all.return_value = [next_truck]

    payload = {"order_id": "order_007", "reason": "high_degradation"}

    await processor.process(
        "truck", "truck_01", "refuse_contract", payload, current_tick=5
    )

    mock_event_repo.create.assert_called_once()
    event_data = mock_event_repo.create.call_args[0][0]
    assert event_data["event_type"] == "contract_proposal"
    assert event_data["entity_type"] == "truck"
    assert event_data["entity_id"] == "truck_02"


# --- Tests: effect failure does not raise ---


@pytest.mark.asyncio
async def test_effect_failure_does_not_raise(processor, mock_warehouse_service):
    mock_warehouse_service.confirm_order.side_effect = Exception("DB connection lost")

    payload = {"order_id": "order_007", "quantity_tons": 50, "eta_ticks": 3}

    await processor.process(
        "warehouse", "wh_01", "confirm_order", payload, current_tick=5
    )
