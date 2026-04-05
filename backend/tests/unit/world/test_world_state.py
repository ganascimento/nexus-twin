import pytest
from datetime import datetime
from pydantic import ValidationError

from src.world.state import WorldState
from src.world.entities.material import Material
from src.world.entities.factory import Factory, FactoryProduct, FactoryPartnerWarehouse
from src.world.entities.warehouse import Warehouse, WarehouseStock
from src.world.entities.store import Store, StoreStock
from src.world.entities.truck import Truck, TruckCargo, TruckRoute


def make_material() -> Material:
    return Material(id="mat-001", name="tijolos", is_active=True)


def make_factory() -> Factory:
    return Factory(
        id="fac-001",
        name="Fábrica Campinas",
        lat=-22.9056,
        lng=-47.0608,
        status="operating",
        products={
            "mat-001": FactoryProduct(
                stock=500.0,
                stock_reserved=50.0,
                stock_max=1000.0,
                production_rate_max=100.0,
                production_rate_current=80.0,
            )
        },
        partner_warehouses=[
            FactoryPartnerWarehouse(warehouse_id="wh-001", priority=1)
        ],
    )


def make_warehouse() -> Warehouse:
    return Warehouse(
        id="wh-001",
        name="Armazém Ribeirão Preto",
        lat=-21.1775,
        lng=-47.8103,
        region="interior",
        capacity_total=2000.0,
        status="operating",
        stocks={
            "mat-001": WarehouseStock(stock=300.0, stock_reserved=30.0, min_stock=100.0)
        },
    )


def make_store() -> Store:
    return Store(
        id="str-001",
        name="Loja SP Capital",
        lat=-23.5505,
        lng=-46.6333,
        status="open",
        stocks={
            "mat-001": StoreStock(stock=50.0, demand_rate=5.0, reorder_point=20.0)
        },
    )


def make_truck_proprietario() -> Truck:
    return Truck(
        id="trk-001",
        truck_type="proprietario",
        capacity_tons=20.0,
        base_lat=-22.9056,
        base_lng=-47.0608,
        current_lat=-22.9056,
        current_lng=-47.0608,
        degradation=0.2,
        breakdown_risk=0.02,
        status="idle",
        factory_id="fac-001",
    )


def make_truck_terceiro() -> Truck:
    return Truck(
        id="trk-002",
        truck_type="terceiro",
        capacity_tons=25.0,
        base_lat=-23.5505,
        base_lng=-46.6333,
        current_lat=-23.5505,
        current_lng=-46.6333,
        degradation=0.1,
        breakdown_risk=0.01,
        status="idle",
        factory_id=None,
    )


class TestWorldStateConstruction:
    def test_full_world_state_is_valid(self):
        ws = WorldState(
            tick=1,
            simulated_timestamp=datetime(2024, 1, 1, 8, 0, 0),
            materials=[make_material()],
            factories=[make_factory()],
            warehouses=[make_warehouse()],
            stores=[make_store()],
            trucks=[make_truck_proprietario(), make_truck_terceiro()],
        )
        assert ws.tick == 1
        assert len(ws.materials) == 1
        assert len(ws.factories) == 1
        assert len(ws.warehouses) == 1
        assert len(ws.stores) == 1
        assert len(ws.trucks) == 2

    def test_empty_world_state_is_valid(self):
        ws = WorldState(
            tick=0,
            simulated_timestamp=datetime.now(),
            materials=[],
            factories=[],
            warehouses=[],
            stores=[],
            trucks=[],
        )
        assert ws.tick == 0
        assert ws.materials == []
        assert ws.trucks == []

    def test_world_state_is_immutable_tick(self):
        ws = WorldState(
            tick=1,
            simulated_timestamp=datetime.now(),
            materials=[],
            factories=[],
            warehouses=[],
            stores=[],
            trucks=[],
        )
        with pytest.raises((ValidationError, TypeError)):
            ws.tick = 99

    def test_world_state_is_immutable_materials(self):
        ws = WorldState(
            tick=1,
            simulated_timestamp=datetime.now(),
            materials=[],
            factories=[],
            warehouses=[],
            stores=[],
            trucks=[],
        )
        with pytest.raises((ValidationError, TypeError)):
            ws.materials = [make_material()]


class TestTruckVariants:
    def test_proprietario_truck_with_factory_id_is_valid(self):
        truck = make_truck_proprietario()
        assert truck.truck_type == "proprietario"
        assert truck.factory_id == "fac-001"

    def test_terceiro_truck_with_null_factory_id_is_valid(self):
        truck = make_truck_terceiro()
        assert truck.truck_type == "terceiro"
        assert truck.factory_id is None

    def test_truck_with_cargo_is_valid(self):
        cargo = TruckCargo(
            material_id="mat-001",
            quantity_tons=15.0,
            origin_type="factory",
            origin_id="fac-001",
            destination_type="warehouse",
            destination_id="wh-001",
        )
        truck = Truck(
            id="trk-003",
            truck_type="proprietario",
            capacity_tons=20.0,
            base_lat=-22.9056,
            base_lng=-47.0608,
            current_lat=-22.9056,
            current_lng=-47.0608,
            degradation=0.3,
            breakdown_risk=0.03,
            status="in_transit",
            factory_id="fac-001",
            cargo=cargo,
        )
        assert truck.cargo is not None
        assert truck.cargo.quantity_tons == 15.0

    def test_truck_with_active_route_is_valid(self):
        route = TruckRoute(
            route_id="rte-001",
            path=[[-22.9056, -47.0608], [-23.5015, -47.4526]],
            timestamps=[0, 7200000],
            eta_ticks=2,
        )
        truck = Truck(
            id="trk-004",
            truck_type="terceiro",
            capacity_tons=25.0,
            base_lat=-22.9056,
            base_lng=-47.0608,
            current_lat=-22.9056,
            current_lng=-47.0608,
            degradation=0.1,
            breakdown_risk=0.01,
            status="in_transit",
            active_route=route,
        )
        assert truck.active_route is not None
        assert truck.active_route.eta_ticks == 2


class TestEntityModels:
    def test_material_fields(self):
        m = make_material()
        assert m.id == "mat-001"
        assert m.name == "tijolos"
        assert m.is_active is True

    def test_factory_product_fields(self):
        p = FactoryProduct(
            stock=100.0,
            stock_reserved=10.0,
            stock_max=500.0,
            production_rate_max=50.0,
            production_rate_current=40.0,
        )
        assert p.stock == 100.0
        assert p.production_rate_current == 40.0

    def test_warehouse_stock_fields(self):
        s = WarehouseStock(stock=200.0, stock_reserved=20.0, min_stock=50.0)
        assert s.min_stock == 50.0

    def test_store_stock_fields(self):
        s = StoreStock(stock=30.0, demand_rate=3.0, reorder_point=10.0)
        assert s.demand_rate == 3.0

    def test_factory_partner_warehouse(self):
        pw = FactoryPartnerWarehouse(warehouse_id="wh-002", priority=2)
        assert pw.priority == 2
