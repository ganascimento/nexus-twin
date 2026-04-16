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
from src.simulation.events import (
    ENGINE_BLOCKED_DEGRADED_TRUCK,
    LOW_STOCK_TRIGGER,
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
                    if route.path and route.timestamps:
                        final_lng, final_lat = route.path[-1]
                        await truck_repo.update_position(truck.id, final_lat, final_lng)
                    await truck_repo.update_status(truck.id, "idle")
                    await truck_repo.set_cargo(truck.id, None)
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

            for truck in world_state.trucks:
                active_events = await event_repo.get_active_for_entity(
                    "truck", truck.id
                )
                if active_events:
                    triggers.append(
                        (
                            self._make_agent_callable("truck", truck.id),
                            trigger_event(
                                "truck",
                                truck.id,
                                active_events[0].event_type,
                                self._tick,
                            ),
                        )
                    )

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

    async def _dispatch_agent(self, agent_fn, event) -> None:
        async with self._semaphore:
            if agent_fn is not None:
                try:
                    await agent_fn(event)
                except Exception as exc:
                    logger.error("Agent dispatch failed for {}: {}", event, exc)
