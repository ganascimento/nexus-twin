import asyncio
import os

from src.enums import TruckStatus
from src.repositories.event import EventRepository
from src.repositories.factory import FactoryRepository
from src.repositories.order import OrderRepository
from src.repositories.store import StoreRepository
from src.repositories.truck import TruckRepository
from src.simulation.events import (
    ENGINE_BLOCKED_DEGRADED_TRUCK,
    LOW_STOCK_TRIGGER,
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


class SimulationEngine:
    DEGRADATION_FACTOR = 1000.0

    def __init__(self, world_state_service, publisher_redis_client, session_factory):
        self._world_state_service = world_state_service
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
            await self.run_tick()
            await asyncio.sleep(self._tick_interval)

    def stop(self) -> None:
        self._running = False

    async def advance_one_tick(self) -> None:
        if self._running:
            raise RuntimeError("stop the engine before advancing manually")
        await self.run_tick()

    async def run_tick(self) -> None:
        self._tick += 1
        world_state = await self._world_state_service.load()
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

                route = truck.active_route

                if route.eta_ticks == 0:
                    await truck_repo.update_status(truck.id, "idle")
                    await truck_repo.set_cargo(truck.id, None)
                    await truck_repo.set_active_route(truck.id, None)
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
                    cargo_tons = truck.cargo.quantity_tons if truck.cargo else 0.0
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
                                None,
                                trigger_event(
                                    "store", store.id, LOW_STOCK_TRIGGER, self._tick
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
                            None,
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
                await agent_fn(event)
