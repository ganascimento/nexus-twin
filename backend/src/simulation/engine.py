import asyncio
import os

from loguru import logger

from src.agents.factory_agent import FactoryAgent
from src.agents.store_agent import StoreAgent
from src.agents.truck_agent import TruckAgent
from src.agents.warehouse_agent import WarehouseAgent
from src.enums import TruckStatus
from src.repositories.event import EventRepository
from src.repositories.factory import FactoryRepository
from src.repositories.order import OrderRepository
from src.repositories.route import RouteRepository
from src.repositories.store import StoreRepository
from src.repositories.truck import TruckRepository
from src.repositories.warehouse import WarehouseRepository
from src.simulation.events import (
    ENGINE_BLOCKED_DEGRADED_TRUCK,
    LOW_STOCK_TRIGGER,
    ORDER_RECEIVED,
    ORDER_RETRY_ELIGIBLE,
    RESUPPLY_REQUESTED,
    ROUTE_BLOCKED,
    STOCK_TRIGGER_FACTORY,
    STOCK_TRIGGER_WAREHOUSE,
    route_event,
    trigger_event,
)
from src.simulation.publisher import publish_event, publish_world_state
from src.world.physics import (
    calculate_breakdown_risk,
    calculate_degradation_delta,
    calculate_distance_km,
    calculate_eta_ticks,
    evaluate_replenishment_trigger,
    is_trip_blocked,
    roll_breakdown,
)
from src.world.state import WorldState

AGENT_MAP = {
    "store": StoreAgent,
    "warehouse": WarehouseAgent,
    "factory": FactoryAgent,
    "truck": TruckAgent,
}


class SimulationEngine:
    DEGRADATION_FACTOR = 1000.0

    def __init__(self, publisher_redis_client, session_factory):
        self._publisher_redis_client = publisher_redis_client
        self._session_factory = session_factory
        self._running: bool = False
        self._tick: int = 0
        self._tick_interval: float = float(os.getenv("TICK_INTERVAL_SECONDS", "10.0"))
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(
            int(os.getenv("MAX_AGENT_WORKERS", "4"))
        )

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.run_tick()
            except Exception as exc:
                logger.error("Engine tick {} failed: {}", self._tick, exc, exc_info=True)
                self._running = False
                return
            await asyncio.sleep(self._tick_interval)

    def stop(self) -> None:
        self._running = False

    async def advance_one_tick(self) -> None:
        if self._running:
            raise RuntimeError("stop the engine before advancing manually")
        await self.run_tick()

    async def run_tick(self) -> None:
        self._tick += 1
        from src.services.world_state import WorldStateService

        async with self._session_factory() as session:
            world_state_service = WorldStateService(session)
            world_state = await world_state_service.load(self._tick)

        await self._apply_physics(world_state)
        triggers = await self._evaluate_triggers(world_state)
        for agent_fn, event in triggers:
            asyncio.create_task(self._dispatch_agent(agent_fn, event))
        await publish_world_state(world_state, self._tick, self._publisher_redis_client)

    async def _apply_physics(self, world_state: WorldState) -> None:
        async with self._session_factory() as session:
            truck_repo = TruckRepository(session)
            store_repo = StoreRepository(session)
            factory_repo = FactoryRepository(session)
            order_repo = OrderRepository(session)
            route_repo = RouteRepository(session)
            warehouse_repo = WarehouseRepository(session)
            event_repo = EventRepository(session)

            for truck in world_state.trucks:
                if truck.status != TruckStatus.MAINTENANCE:
                    continue
                if truck.maintenance_start_tick is None:
                    await truck_repo.update_status(truck.id, "idle")
                    await truck_repo.clear_maintenance_info(truck.id)
                    logger.warning("Truck {} in maintenance without tracking, forcing idle", truck.id)
                    continue
                if self._tick - truck.maintenance_start_tick >= truck.maintenance_duration_ticks:
                    await truck_repo.update_status(truck.id, "idle")
                    await truck_repo.clear_maintenance_info(truck.id)
                    await event_repo.create({
                        "event_type": "truck_maintenance_completed",
                        "source": "engine",
                        "entity_type": "truck",
                        "entity_id": truck.id,
                        "payload": {},
                        "status": "active",
                        "tick_start": self._tick,
                    })

            for truck in world_state.trucks:
                if truck.status != TruckStatus.IN_TRANSIT:
                    continue

                if is_trip_blocked(truck.degradation):
                    await truck_repo.update_status(truck.id, "idle")
                    await publish_event(
                        route_event(
                            ENGINE_BLOCKED_DEGRADED_TRUCK, truck.id, {}, self._tick
                        ),
                        self._publisher_redis_client,
                    )
                    continue

                route = await route_repo.get_active_by_truck(truck.id)
                if route is None:
                    logger.warning("Truck {} is IN_TRANSIT but has no active route", truck.id)
                    continue

                new_eta = max(0, route.eta_ticks - 1)
                await route_repo.update_eta_ticks(route.id, new_eta)

                if new_eta == 0:
                    cargo = truck.cargo
                    if cargo is not None:
                        if isinstance(cargo, dict):
                            material_id = cargo.get("material_id")
                            quantity_tons = cargo.get("quantity_tons", 0.0)
                        else:
                            material_id = getattr(cargo, "material_id", None)
                            quantity_tons = getattr(cargo, "quantity_tons", 0.0)
                        if material_id and quantity_tons > 0:
                            if route.dest_type == "warehouse":
                                await warehouse_repo.update_stock(
                                    route.dest_id, material_id, quantity_tons
                                )
                            elif route.dest_type == "store":
                                await store_repo.update_stock(
                                    route.dest_id, material_id, quantity_tons
                                )
                            else:
                                logger.warning(
                                    "Truck {} arrived at unsupported dest_type '{}', skipping stock transfer",
                                    truck.id, route.dest_type,
                                )

                    if route.order_id is not None:
                        await order_repo.update_status(route.order_id, "delivered")

                    if route.dest_type in ("warehouse", "store"):
                        delivery_payload = {}
                        if cargo is not None:
                            if isinstance(cargo, dict):
                                delivery_payload = {
                                    "material_id": cargo.get("material_id"),
                                    "quantity_tons": cargo.get("quantity_tons"),
                                    "from_truck_id": truck.id,
                                }
                            else:
                                delivery_payload = {
                                    "material_id": getattr(cargo, "material_id", None),
                                    "quantity_tons": getattr(cargo, "quantity_tons", None),
                                    "from_truck_id": truck.id,
                                }
                        await event_repo.create({
                            "event_type": "resupply_delivered",
                            "entity_type": route.dest_type,
                            "entity_id": route.dest_id,
                            "source": "engine",
                            "status": "active",
                            "tick_start": self._tick,
                            "payload": delivery_payload,
                        })

                    await event_repo.create({
                        "event_type": "truck_arrived",
                        "entity_type": "truck",
                        "entity_id": truck.id,
                        "source": "engine",
                        "status": "active",
                        "tick_start": self._tick,
                        "payload": {
                            "route_id": str(route.id),
                            "dest_type": route.dest_type,
                            "dest_id": route.dest_id,
                        },
                    })

                    if route.path and route.timestamps:
                        final_lng, final_lat = route.path[-1]
                        await truck_repo.update_position(truck.id, final_lat, final_lng)
                    await truck_repo.set_cargo(truck.id, None)
                    await truck_repo.update_status(truck.id, "idle")
                    await truck_repo.set_active_route(truck.id, None)
                    await route_repo.update_status(route.id, "completed")
                else:
                    path = route.path
                    timestamps = route.timestamps

                    new_lng, new_lat = self._interpolate_position(
                        path, timestamps, self._tick
                    )

                    await truck_repo.update_position(truck.id, new_lat, new_lng)

                    distance_km = calculate_distance_km(
                        truck.current_lat, truck.current_lng, new_lat, new_lng
                    )
                    if truck.cargo is None:
                        cargo_tons = 0.0
                    elif isinstance(truck.cargo, dict):
                        cargo_tons = truck.cargo.get("quantity_tons", 0.0)
                    else:
                        cargo_tons = getattr(truck.cargo, "quantity_tons", 0.0)
                    delta = calculate_degradation_delta(
                        distance_km, cargo_tons, truck.capacity_tons
                    )
                    new_degradation = truck.degradation + delta
                    new_breakdown_risk = calculate_breakdown_risk(new_degradation)
                    await truck_repo.update_degradation(
                        truck.id, new_degradation, new_breakdown_risk
                    )

                    if roll_breakdown(new_breakdown_risk):
                        await truck_repo.update_status(truck.id, "broken")
                        await event_repo.create({
                            "event_type": "truck_breakdown",
                            "source": "engine",
                            "entity_type": "truck",
                            "entity_id": truck.id,
                            "payload": {
                                "route_id": str(route.id),
                                "lat": new_lat,
                                "lng": new_lng,
                            },
                            "status": "active",
                            "tick_start": self._tick,
                        })
                        continue

            for store in world_state.stores:
                for material_id, stock_entry in store.stocks.items():
                    delta = -min(stock_entry.demand_rate, stock_entry.stock)
                    await store_repo.update_stock(store.id, material_id, delta)

            for factory in world_state.factories:
                for material_id, product in factory.products.items():
                    if product.stock >= product.stock_max:
                        await factory_repo.update_production_rate(
                            factory.id, material_id, 0.0
                        )
                    else:
                        delta = min(
                            product.production_rate_current,
                            product.stock_max - product.stock,
                        )
                        await factory_repo.update_product_stock(
                            factory.id, material_id, delta
                        )

            await order_repo.increment_all_age_ticks()

            await session.commit()

    def _interpolate_position(
        self, path: list, timestamps: list, current_tick: int
    ) -> tuple[float, float]:
        if not path or not timestamps:
            return 0.0, 0.0
        if current_tick <= timestamps[0]:
            return path[0][0], path[0][1]
        if current_tick >= timestamps[-1]:
            return path[-1][0], path[-1][1]

        for i in range(len(timestamps) - 1):
            t0 = timestamps[i]
            t1 = timestamps[i + 1]
            if t0 <= current_tick < t1:
                progress = (current_tick - t0) / (t1 - t0)
                lng0, lat0 = path[i]
                lng1, lat1 = path[i + 1]
                new_lng = lng0 + progress * (lng1 - lng0)
                new_lat = lat0 + progress * (lat1 - lat0)
                return new_lng, new_lat

        return path[-1][0], path[-1][1]

    def _make_agent_callable(self, entity_type: str, entity_id: str):
        async def _run(event):
            agent_class = AGENT_MAP.get(entity_type)
            if agent_class is None:
                return
            async with self._session_factory() as session:
                agent = agent_class(entity_id, session, self._publisher_redis_client)
                await agent.run_cycle(event)
                await session.commit()
        return _run

    async def _evaluate_triggers(self, world_state: WorldState) -> list[tuple]:
        triggers = []

        async with self._session_factory() as session:
            event_repo = EventRepository(session)
            order_repo = OrderRepository(session)
            truck_repo = TruckRepository(session)

            for store in world_state.stores:
                triggered = False
                for material_id, stock_entry in store.stocks.items():
                    nearest_warehouse = self._find_nearest_warehouse_with_stock(
                        store, material_id, world_state.warehouses
                    )
                    if nearest_warehouse is not None:
                        lead_time_ticks = self._estimate_lead_time_ticks(
                            store.lat,
                            store.lng,
                            nearest_warehouse.lat,
                            nearest_warehouse.lng,
                        )
                    else:
                        lead_time_ticks = self._estimate_lead_time_ticks(
                            store.lat, store.lng, store.lat, store.lng
                        )

                    should_trigger = evaluate_replenishment_trigger(
                        stock_entry.stock,
                        stock_entry.reorder_point,
                        stock_entry.demand_rate,
                        lead_time_ticks,
                    )
                    if should_trigger and not triggered:
                        triggers.append(
                            (
                                self._make_agent_callable("store", store.id),
                                trigger_event(
                                    "store", store.id, LOW_STOCK_TRIGGER, self._tick
                                ),
                            )
                        )
                        triggered = True

            for store in world_state.stores:
                retry_eligible = await order_repo.get_retry_eligible(store.id)
                if retry_eligible:
                    order = retry_eligible[0]
                    triggers.append(
                        (
                            self._make_agent_callable("store", store.id),
                            trigger_event(
                                "store", store.id, ORDER_RETRY_ELIGIBLE, self._tick,
                                payload={
                                    "order_id": str(order.id),
                                    "material_id": order.material_id,
                                    "original_target_id": order.target_id,
                                },
                            ),
                        )
                    )
                    await order_repo.clear_retry_after_tick(order.id)

            for warehouse in world_state.warehouses:
                triggered = False
                for material_id, stock_entry in warehouse.stocks.items():
                    available = stock_entry.stock - stock_entry.stock_reserved
                    if stock_entry.min_stock > 0 and available <= stock_entry.min_stock * 1.2:
                        if not triggered:
                            triggers.append(
                                (
                                    self._make_agent_callable("warehouse", warehouse.id),
                                    trigger_event(
                                        "warehouse", warehouse.id, STOCK_TRIGGER_WAREHOUSE, self._tick
                                    ),
                                )
                            )
                            triggered = True

            for warehouse in world_state.warehouses:
                untriggered_orders = await order_repo.get_untriggered_for_target(warehouse.id)
                for order in untriggered_orders:
                    order_payload = {
                        "order_id": str(order.id),
                        "requester_type": order.requester_type,
                        "requester_id": order.requester_id,
                        "material_id": order.material_id,
                        "quantity_tons": order.quantity_tons,
                    }
                    triggers.append(
                        (
                            self._make_agent_callable("warehouse", warehouse.id),
                            trigger_event(
                                "warehouse", warehouse.id, ORDER_RECEIVED, self._tick,
                                payload=order_payload,
                            ),
                        )
                    )
                    await order_repo.mark_triggered(order.id, self._tick)

            for factory in world_state.factories:
                triggered = False
                for material_id, product in factory.products.items():
                    if product.stock_max > 0 and product.stock / product.stock_max < 0.3 and product.production_rate_current == 0:
                        if not triggered:
                            triggers.append(
                                (
                                    self._make_agent_callable("factory", factory.id),
                                    trigger_event(
                                        "factory", factory.id, STOCK_TRIGGER_FACTORY, self._tick
                                    ),
                                )
                            )
                            triggered = True

            for factory in world_state.factories:
                untriggered_orders = await order_repo.get_untriggered_for_target(factory.id)
                for order in untriggered_orders:
                    order_payload = {
                        "order_id": str(order.id),
                        "requester_type": order.requester_type,
                        "requester_id": order.requester_id,
                        "material_id": order.material_id,
                        "quantity_tons": order.quantity_tons,
                    }
                    triggers.append(
                        (
                            self._make_agent_callable("factory", factory.id),
                            trigger_event(
                                "factory", factory.id, RESUPPLY_REQUESTED, self._tick,
                                payload=order_payload,
                            ),
                        )
                    )
                    await order_repo.mark_triggered(order.id, self._tick)

            for factory in world_state.factories:
                triggered_orders = await order_repo.get_triggered_but_pending_for_target(factory.id)
                for order in triggered_orders:
                    factory_product = factory.products.get(order.material_id)
                    if factory_product and factory_product.stock >= order.quantity_tons:
                        await order_repo.reset_triggered(order.id)

            for factory in world_state.factories:
                active_events = await event_repo.get_active_for_entity(
                    "factory", factory.id
                )
                for evt in active_events:
                    triggers.append(
                        (
                            self._make_agent_callable("factory", factory.id),
                            trigger_event(
                                "factory",
                                factory.id,
                                evt.event_type,
                                self._tick,
                                payload=evt.payload or {},
                            ),
                        )
                    )
                    await event_repo.resolve(evt.id, self._tick)

            for warehouse in world_state.warehouses:
                active_events = await event_repo.get_active_for_entity(
                    "warehouse", warehouse.id
                )
                for evt in active_events:
                    triggers.append(
                        (
                            self._make_agent_callable("warehouse", warehouse.id),
                            trigger_event(
                                "warehouse",
                                warehouse.id,
                                evt.event_type,
                                self._tick,
                                payload=evt.payload or {},
                            ),
                        )
                    )
                    await event_repo.resolve(evt.id, self._tick)

            for store in world_state.stores:
                active_events = await event_repo.get_active_for_entity(
                    "store", store.id
                )
                for evt in active_events:
                    triggers.append(
                        (
                            self._make_agent_callable("store", store.id),
                            trigger_event(
                                "store",
                                store.id,
                                evt.event_type,
                                self._tick,
                                payload=evt.payload or {},
                            ),
                        )
                    )
                    await event_repo.resolve(evt.id, self._tick)

            for truck in world_state.trucks:
                active_events = await event_repo.get_active_for_entity(
                    "truck", truck.id
                )
                for evt in active_events:
                    triggers.append(
                        (
                            self._make_agent_callable("truck", truck.id),
                            trigger_event(
                                "truck",
                                truck.id,
                                evt.event_type,
                                self._tick,
                                payload=evt.payload or {},
                            ),
                        )
                    )
                    await event_repo.resolve(evt.id, self._tick)

            blocked_events = await event_repo.get_active_by_type("route_blocked")
            for blocked_evt in blocked_events:
                for truck in world_state.trucks:
                    if truck.status != TruckStatus.IN_TRANSIT:
                        continue
                    triggers.append(
                        (
                            self._make_agent_callable("truck", truck.id),
                            trigger_event(
                                "truck", truck.id, ROUTE_BLOCKED, self._tick,
                                payload=blocked_evt.payload or {},
                            ),
                        )
                    )
                await event_repo.resolve(blocked_evt.id, self._tick)

            orphaned_orders = await order_repo.get_confirmed_without_route(limit=10)
            for order in orphaned_orders:
                truck = None
                event_type = None

                if order.target_type == "factory":
                    truck = await truck_repo.get_idle_by_factory(order.target_id)
                    if truck:
                        event_type = "new_order"

                if truck is None:
                    target_entity = self._find_entity_in_world_state(
                        world_state, order.target_type, order.target_id
                    )
                    if target_entity:
                        truck = await truck_repo.get_nearest_idle_third_party(
                            target_entity.lat, target_entity.lng
                        )
                    else:
                        truck = await truck_repo.get_nearest_idle_third_party(0.0, 0.0)
                    if truck:
                        event_type = "contract_proposal"

                if truck is None:
                    continue

                existing = await event_repo.get_active_for_entity("truck", truck.id)
                if any(
                    (e.payload or {}).get("order_id") == str(order.id)
                    for e in existing
                ):
                    continue

                await event_repo.create({
                    "event_type": event_type,
                    "source": "engine",
                    "entity_type": "truck",
                    "entity_id": truck.id,
                    "payload": {
                        "order_id": str(order.id),
                        "material_id": order.material_id,
                        "quantity_tons": order.quantity_tons,
                        "target_type": order.target_type,
                        "target_id": order.target_id,
                        "requester_type": order.requester_type,
                        "requester_id": order.requester_id,
                    },
                    "status": "active",
                    "tick_start": self._tick,
                })

            await session.commit()

        return triggers

    def _find_nearest_warehouse_with_stock(self, store, material_id: str, warehouses):
        nearest = None
        min_distance = float("inf")
        for wh in warehouses:
            if material_id in wh.stocks:
                distance = calculate_distance_km(store.lat, store.lng, wh.lat, wh.lng)
                if distance < min_distance:
                    min_distance = distance
                    nearest = wh
        return nearest

    def _estimate_lead_time_ticks(
        self, from_lat: float, from_lng: float, to_lat: float, to_lng: float
    ) -> int:
        distance_km = calculate_distance_km(from_lat, from_lng, to_lat, to_lng)
        return calculate_eta_ticks(distance_km)

    def _find_entity_in_world_state(self, world_state, entity_type, entity_id):
        if entity_type == "warehouse":
            for wh in world_state.warehouses:
                if wh.id == entity_id:
                    return wh
        elif entity_type == "factory":
            for f in world_state.factories:
                if f.id == entity_id:
                    return f
        elif entity_type == "store":
            for s in world_state.stores:
                if s.id == entity_id:
                    return s
        return None

    async def _dispatch_agent(self, agent_fn, event) -> None:
        async with self._semaphore:
            if agent_fn is not None:
                try:
                    await agent_fn(event)
                except Exception as exc:
                    logger.error("Agent dispatch failed for {}: {}", event, exc)
