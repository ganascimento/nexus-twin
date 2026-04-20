from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import WorldStateSlice, build_agent_graph
from src.guardrails.store import StoreDecision
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

    async def _build_world_state_slice(self, current_tick: int) -> WorldStateSlice:
        store = await StoreRepository(self._db_session).get_by_id(self._entity_id)
        warehouses = await WarehouseRepository(self._db_session).get_all()
        orders = await OrderRepository(self._db_session).get_pending_for_requester(
            self._entity_id
        )
        events = await EventRepository(self._db_session).get_active_for_entity(
            "store", self._entity_id
        )

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
            "name": store.name,
            "stocks": stocks,
        }

        related_entities = [
            {"id": w.id, "name": w.name, "region": w.region} for w in warehouses[:10]
        ]

        pending_orders = [
            {"id": str(o.id), "requester_id": o.requester_id, "status": o.status}
            for o in orders
        ]

        active_events = [
            {"id": str(e.id), "event_type": e.event_type, "status": e.status}
            for e in events
        ]

        return WorldStateSlice(
            entity=entity,
            related_entities=related_entities,
            active_events=active_events,
            pending_orders=pending_orders,
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
        world_state_slice = await self._build_world_state_slice(trigger.tick)

        initial_state = {
            "entity_id": self._entity_id,
            "entity_type": "store",
            "trigger_event": trigger.event_type,
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
        return await graph.ainvoke(initial_state)
