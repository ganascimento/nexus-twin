from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.decision_effect_processor import DecisionEffectProcessor


def _make_order(
    id=None,
    requester_type="store",
    requester_id="store-001",
    target_type="warehouse",
    target_id="wh-001",
    material_id="cimento",
    quantity_tons=5.0,
    status="confirmed",
    age_ticks=0,
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
    order.age_ticks = age_ticks
    return order


def _make_truck(id="truck-001", truck_type="terceiro", factory_id=None, capacity_tons=30.0):
    truck = MagicMock()
    truck.id = id
    truck.truck_type = truck_type
    truck.status = "idle"
    truck.factory_id = factory_id
    truck.capacity_tons = capacity_tons
    truck.degradation = 0.2
    truck.current_lat = -23.55
    truck.current_lng = -46.63
    truck.cargo = None
    return truck


def _make_entity(id_, lat=-23.0, lng=-46.0):
    e = MagicMock()
    e.id = id_
    e.lat = lat
    e.lng = lng
    return e


def _build_processor(*, primary_order, truck=None):
    order_repo = AsyncMock()
    order_repo.get_by_id = AsyncMock(return_value=primary_order)
    order_repo.mark_in_transit_bulk = AsyncMock()
    order_repo.rollback_in_transit_bulk = AsyncMock()
    order_repo.has_active_order = AsyncMock(return_value=False)
    order_repo.get_active_by_requester_target_material = AsyncMock(return_value=None)
    order_repo.create = AsyncMock(return_value=primary_order)
    order_repo.update_status = AsyncMock()

    warehouse_service = AsyncMock()
    factory_repo = AsyncMock()
    factory_repo.atomic_reserve_stock = AsyncMock(return_value=True)
    factory_repo.get_by_id = AsyncMock(return_value=_make_entity("factory-001"))
    truck_service = AsyncMock()

    route_service = AsyncMock()
    route_service.compute_route = AsyncMock(
        return_value={
            "path": [[-46.63, -23.55], [-46.0, -23.0]],
            "timestamps": [0, 5],
            "distance_km": 100,
            "eta_ticks": 3,
        }
    )
    created_route = MagicMock()
    created_route.id = uuid4()
    route_service.create_route = AsyncMock(return_value=created_route)

    event_repo = AsyncMock()
    event_repo.create = AsyncMock()

    t = truck or _make_truck()
    truck_repo = AsyncMock()
    truck_repo.get_all = AsyncMock(return_value=[t])
    truck_repo.get_by_id = AsyncMock(return_value=t)
    truck_repo.get_by_factory = AsyncMock(return_value=[])
    truck_repo.get_idle_third_party_for_load = AsyncMock(return_value=t)
    truck_repo.set_cargo = AsyncMock()
    truck_repo.set_active_route = AsyncMock()

    warehouse_repo = AsyncMock()
    warehouse_repo.get_by_id = AsyncMock(return_value=_make_entity("wh-001"))

    store_repo = AsyncMock()
    store_repo.get_by_id = AsyncMock(return_value=_make_entity("store-001"))

    route_repo = AsyncMock()
    route_repo.get_active_by_truck = AsyncMock(return_value=None)
    route_repo.update_status = AsyncMock()

    processor = DecisionEffectProcessor(
        session=AsyncMock(),
        order_repo=order_repo,
        warehouse_service=warehouse_service,
        factory_repo=factory_repo,
        truck_service=truck_service,
        route_service=route_service,
        event_repo=event_repo,
        truck_repo=truck_repo,
        warehouse_repo=warehouse_repo,
        store_repo=store_repo,
        route_repo=route_repo,
    )
    return processor, {
        "order_repo": order_repo,
        "event_repo": event_repo,
        "truck_service": truck_service,
        "truck_repo": truck_repo,
        "route_repo": route_repo,
    }


# --- confirm_order: handler emits single-entry manifest + max_age_ticks ---


@pytest.mark.asyncio
async def test_confirm_order_payload_carries_single_entry_manifest():
    primary = _make_order(material_id="cimento", quantity_tons=5.0, age_ticks=2)
    processor, mocks = _build_processor(primary_order=primary)

    await processor.process(
        "warehouse",
        "wh-001",
        "confirm_order",
        {"order_id": str(primary.id), "quantity_tons": 5.0, "eta_ticks": 3},
        current_tick=10,
    )

    mocks["event_repo"].create.assert_called_once()
    event_data = mocks["event_repo"].create.call_args[0][0]
    assert event_data["event_type"] == "contract_proposal"

    payload = event_data["payload"]
    assert payload["quantity_tons"] == 5.0
    manifest = payload["orders_manifest"]
    assert len(manifest) == 1
    assert manifest[0]["order_id"] == str(primary.id)
    assert manifest[0]["material_id"] == "cimento"
    assert manifest[0]["quantity_tons"] == 5.0


@pytest.mark.asyncio
async def test_confirm_order_payload_carries_max_age_ticks():
    primary = _make_order(material_id="cimento", quantity_tons=5.0, age_ticks=4)
    processor, mocks = _build_processor(primary_order=primary)

    await processor.process(
        "warehouse",
        "wh-001",
        "confirm_order",
        {"order_id": str(primary.id), "quantity_tons": 5.0, "eta_ticks": 3},
        current_tick=10,
    )

    payload = mocks["event_repo"].create.call_args[0][0]["payload"]
    assert payload["max_age_ticks"] == 4


# --- send_stock: handler emits single-entry manifest + max_age_ticks ---


@pytest.mark.asyncio
async def test_send_stock_payload_carries_single_entry_manifest_and_age():
    primary = _make_order(
        requester_type="warehouse",
        requester_id="wh-001",
        target_type="factory",
        target_id="factory-001",
        material_id="cimento",
        quantity_tons=10.0,
        age_ticks=2,
    )
    processor, mocks = _build_processor(primary_order=primary)
    mocks["order_repo"].get_active_by_requester_target_material.return_value = primary

    await processor.process(
        "factory",
        "factory-001",
        "send_stock",
        {
            "material_id": "cimento",
            "destination_warehouse_id": "wh-001",
            "quantity_tons": 10.0,
        },
        current_tick=10,
    )

    mocks["event_repo"].create.assert_called_once()
    payload = mocks["event_repo"].create.call_args[0][0]["payload"]
    assert payload["quantity_tons"] == 10.0
    manifest = payload["orders_manifest"]
    assert len(manifest) == 1
    assert manifest[0]["material_id"] == "cimento"
    assert payload["max_age_ticks"] == 2


# --- accept_contract: marks all manifest orders IN_TRANSIT ---


@pytest.mark.asyncio
async def test_accept_contract_marks_all_manifest_orders_in_transit():
    primary = _make_order(material_id="cimento", quantity_tons=5.0)
    sibling_id = uuid4()

    truck = _make_truck(id="truck-001")
    processor, mocks = _build_processor(primary_order=primary, truck=truck)

    manifest = [
        {"order_id": str(primary.id), "material_id": "cimento", "quantity_tons": 5.0},
        {"order_id": str(sibling_id), "material_id": "vergalhao", "quantity_tons": 3.0},
    ]

    await processor.process(
        "truck",
        "truck-001",
        "accept_contract",
        {
            "order_id": str(primary.id),
            "chosen_route_risk_level": "low",
            "orders_manifest": manifest,
        },
        current_tick=10,
    )

    mocks["order_repo"].mark_in_transit_bulk.assert_called_once()
    called_ids = mocks["order_repo"].mark_in_transit_bulk.call_args[0][0]
    assert set(str(x) for x in called_ids) == {str(primary.id), str(sibling_id)}


@pytest.mark.asyncio
async def test_accept_contract_cargo_carries_manifest():
    primary = _make_order(material_id="cimento", quantity_tons=5.0)
    sibling_id = uuid4()

    truck = _make_truck(id="truck-001")
    processor, mocks = _build_processor(primary_order=primary, truck=truck)

    manifest = [
        {"order_id": str(primary.id), "material_id": "cimento", "quantity_tons": 5.0},
        {"order_id": str(sibling_id), "material_id": "vergalhao", "quantity_tons": 3.0},
    ]

    await processor.process(
        "truck",
        "truck-001",
        "accept_contract",
        {
            "order_id": str(primary.id),
            "chosen_route_risk_level": "low",
            "orders_manifest": manifest,
        },
        current_tick=10,
    )

    mocks["truck_service"].assign_route.assert_called_once()
    _, _, cargo = mocks["truck_service"].assign_route.call_args[0]
    assert "manifest" in cargo
    assert len(cargo["manifest"]) == 2
    assert cargo["quantity_tons"] == 8.0


@pytest.mark.asyncio
async def test_accept_contract_single_order_backcompat_when_manifest_absent():
    primary = _make_order(material_id="cimento", quantity_tons=5.0)

    truck = _make_truck(id="truck-001")
    processor, mocks = _build_processor(primary_order=primary, truck=truck)

    await processor.process(
        "truck",
        "truck-001",
        "accept_contract",
        {"order_id": str(primary.id), "chosen_route_risk_level": "low"},
        current_tick=10,
    )

    mocks["order_repo"].mark_in_transit_bulk.assert_called_once()
    called_ids = mocks["order_repo"].mark_in_transit_bulk.call_args[0][0]
    assert [str(x) for x in called_ids] == [str(primary.id)]


# --- refuse_contract: preserves manifest to next truck ---


@pytest.mark.asyncio
async def test_refuse_contract_preserves_manifest_to_next_truck():
    primary = _make_order(material_id="cimento", quantity_tons=5.0)
    sibling_id = uuid4()

    truck = _make_truck(id="truck-001")
    processor, mocks = _build_processor(primary_order=primary, truck=truck)

    next_truck = _make_truck(id="truck-002")
    mocks["truck_repo"].get_idle_third_party_for_load.return_value = next_truck

    manifest = [
        {"order_id": str(primary.id), "material_id": "cimento", "quantity_tons": 5.0},
        {"order_id": str(sibling_id), "material_id": "vergalhao", "quantity_tons": 3.0},
    ]

    await processor.process(
        "truck",
        "truck-001",
        "refuse_contract",
        {
            "order_id": str(primary.id),
            "reason": "low_cargo_utilization",
            "orders_manifest": manifest,
        },
        current_tick=10,
    )

    mocks["event_repo"].create.assert_called_once()
    event_data = mocks["event_repo"].create.call_args[0][0]
    assert event_data["entity_id"] == "truck-002"
    assert event_data["event_type"] == "contract_proposal"

    new_payload = event_data["payload"]
    assert new_payload["orders_manifest"] == manifest
    assert new_payload["quantity_tons"] == 8.0


# --- alert_breakdown: rolls back manifest orders to confirmed ---


@pytest.mark.asyncio
async def test_alert_breakdown_rolls_back_manifest_orders_to_confirmed():
    primary = _make_order(material_id="cimento", quantity_tons=5.0, status="in_transit")
    sibling_id = uuid4()

    truck = _make_truck(id="truck-001")
    truck.cargo = {
        "manifest": [
            {"order_id": str(primary.id), "material_id": "cimento", "quantity_tons": 5.0},
            {"order_id": str(sibling_id), "material_id": "vergalhao", "quantity_tons": 3.0},
        ],
        "quantity_tons": 8.0,
    }
    processor, mocks = _build_processor(primary_order=primary, truck=truck)
    mocks["truck_repo"].get_by_id.return_value = truck

    rescue = _make_truck(id="truck-002")
    mocks["truck_repo"].get_all.return_value = [truck, rescue]

    active_route = MagicMock()
    active_route.id = uuid4()
    active_route.status = "active"
    active_route.order_id = primary.id
    active_route.origin_type = "warehouse"
    active_route.origin_id = "wh-001"
    active_route.dest_type = "store"
    active_route.dest_id = "store-001"
    mocks["route_repo"].get_active_by_truck.return_value = active_route

    await processor.process(
        "truck",
        "truck-001",
        "alert_breakdown",
        {"current_degradation": 0.96},
        current_tick=10,
    )

    mocks["order_repo"].rollback_in_transit_bulk.assert_called_once()
    called_ids = mocks["order_repo"].rollback_in_transit_bulk.call_args[0][0]
    assert set(str(x) for x in called_ids) == {str(primary.id), str(sibling_id)}
