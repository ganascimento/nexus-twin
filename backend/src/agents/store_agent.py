from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import WorldStateSlice, build_agent_graph
from src.guardrails.store import StoreDecision
from src.observability.langfuse import build_invoke_config
from src.repositories.event import EventRepository
from src.repositories.factory import FactoryRepository
from src.repositories.order import OrderRepository
from src.repositories.route import RouteRepository
from src.repositories.store import StoreRepository
from src.repositories.truck import TruckRepository
from src.repositories.warehouse import WarehouseRepository
from src.services.decision_effect_processor import DecisionEffectProcessor
from src.services.route import RouteService
from src.services.truck import TruckService
from src.services.warehouse import WarehouseService
from src.tools import STORE_TOOLS


class StoreAgent:
    def __init__(self, entity_id: str, db_session: AsyncSession, publisher):
        self._entity_id = entity_id
        self._db_session = db_session
        self._publisher = publisher

    async def _build_world_state_slice(self, trigger) -> WorldStateSlice:
        store = await StoreRepository(self._db_session).get_by_id(self._entity_id)

        event_type = trigger.event_type
        payload = trigger.payload or {}
        material_of_interest = payload.get("material_id")

        stocks = [
            {
                "material_id": s.material_id,
                "stock": s.stock,
                "demand_rate": s.demand_rate,
                "reorder_point": s.reorder_point,
            }
            for s in store.stocks
        ]

        entity = {
            "id": store.id,
            "stocks": stocks,
            "lat": store.lat,
            "lng": store.lng,
        }

        if event_type in ("low_stock_trigger", "order_retry_eligible", "demand_spike"):
            warehouses = await WarehouseRepository(self._db_session).get_all()
            related_entities = []
            for w in warehouses[:10]:
                filtered_materials = [
                    {
                        "material_id": s.material_id,
                        "stock": s.stock,
                        "stock_reserved": s.stock_reserved,
                    }
                    for s in w.stocks
                    if (not material_of_interest)
                    or s.material_id == material_of_interest
                ]
                if not filtered_materials:
                    continue
                related_entities.append({
                    "id": w.id,
                    "region": w.region,
                    "lat": w.lat,
                    "lng": w.lng,
                    "materials_available": filtered_materials,
                })
        else:
            related_entities = []

        return WorldStateSlice(
            entity=entity,
            related_entities=related_entities,
            active_events=[],
            pending_orders=[],
        )

    def _build_effect_processor(self):
        order_repo = OrderRepository(self._db_session)
        warehouse_repo = WarehouseRepository(self._db_session)
        truck_repo = TruckRepository(self._db_session)
        factory_repo = FactoryRepository(self._db_session)
        event_repo = EventRepository(self._db_session)
        route_repo = RouteRepository(self._db_session)
        store_repo = StoreRepository(self._db_session)
        return DecisionEffectProcessor(
            session=self._db_session,
            order_repo=order_repo,
            warehouse_service=WarehouseService(
                warehouse_repo, order_repo, self._publisher
            ),
            factory_repo=factory_repo,
            truck_service=TruckService(truck_repo, self._publisher),
            route_service=RouteService(route_repo),
            event_repo=event_repo,
            truck_repo=truck_repo,
            warehouse_repo=warehouse_repo,
            store_repo=store_repo,
            route_repo=route_repo,
        )

    async def run_cycle(self, trigger) -> None:
        world_state_slice = await self._build_world_state_slice(trigger)

        initial_state = {
            "entity_id": self._entity_id,
            "entity_type": "store",
            "trigger_event": trigger.event_type,
            "trigger_payload": trigger.payload or {},
            "current_tick": trigger.tick,
            "world_state": world_state_slice,
            "messages": [],
            "decision_history": [],
            "decision": None,
            "fast_path_taken": False,
            "error": None,
        }

        processor = self._build_effect_processor()
        graph = build_agent_graph(
            "store",
            tools=STORE_TOOLS,
            decision_schema_map={"store": StoreDecision},
            db_session=self._db_session,
            publisher_instance=self._publisher,
            decision_effect_processor=processor,
        )
        return await graph.ainvoke(initial_state, config=build_invoke_config(trigger))
