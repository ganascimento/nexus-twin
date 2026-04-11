from src.simulation.events import (
    LOW_STOCK_TRIGGER,
    STOCK_TRIGGER_FACTORY,
    STOCK_TRIGGER_WAREHOUSE,
    SimulationEvent,
    trigger_event,
)
from src.world.physics import calculate_distance_km, calculate_eta_ticks, evaluate_replenishment_trigger


class TriggerEvaluationService:
    async def evaluate_all(self, world_state_dict: dict) -> list[SimulationEvent]:
        triggers: list[SimulationEvent] = []
        tick = world_state_dict.get("tick", 0)

        stores = world_state_dict.get("stores", [])
        warehouses = world_state_dict.get("warehouses", [])
        factories = world_state_dict.get("factories", [])

        for store in stores:
            stocks = store.get("stocks", {})
            for material_id, stock_entry in stocks.items():
                stock = stock_entry.get("stock", 0)
                reorder_point = stock_entry.get("reorder_point", 0)
                demand_rate = stock_entry.get("demand_rate", 0)

                lead_time = self._estimate_lead_time_to_nearest(
                    store, material_id, warehouses
                )

                if evaluate_replenishment_trigger(stock, reorder_point, demand_rate, lead_time):
                    triggers.append(trigger_event("store", store["id"], LOW_STOCK_TRIGGER, tick))
                    break

        for warehouse in warehouses:
            stocks = warehouse.get("stocks", {})
            for material_id, stock_entry in stocks.items():
                stock = stock_entry.get("stock", 0)
                min_stock = stock_entry.get("min_stock", 0)
                stock_reserved = stock_entry.get("stock_reserved", 0)
                available = stock - stock_reserved
                if min_stock > 0 and available <= min_stock * 1.2:
                    triggers.append(trigger_event("warehouse", warehouse["id"], STOCK_TRIGGER_WAREHOUSE, tick))
                    break

        for factory in factories:
            products = factory.get("products", {})
            for material_id, product in products.items():
                stock = product.get("stock", 0)
                stock_max = product.get("stock_max", float("inf"))
                production_rate = product.get("production_rate_current", 0)
                if stock_max > 0 and stock / stock_max < 0.3 and production_rate == 0:
                    triggers.append(trigger_event("factory", factory["id"], STOCK_TRIGGER_FACTORY, tick))
                    break

        return triggers

    def _estimate_lead_time_to_nearest(
        self, store: dict, material_id: str, warehouses: list[dict]
    ) -> int:
        store_lat = store.get("lat", 0)
        store_lng = store.get("lng", 0)
        min_distance = float("inf")

        for wh in warehouses:
            stocks = wh.get("stocks", {})
            if material_id in stocks and stocks[material_id].get("stock", 0) > 0:
                dist = calculate_distance_km(store_lat, store_lng, wh.get("lat", 0), wh.get("lng", 0))
                if dist < min_distance:
                    min_distance = dist

        if min_distance == float("inf"):
            return 10

        return calculate_eta_ticks(min_distance)
