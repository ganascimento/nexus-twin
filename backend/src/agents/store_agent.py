from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import WorldStateSlice, build_agent_graph
from src.guardrails.store import StoreDecision
from src.repositories.event import EventRepository
from src.repositories.order import OrderRepository
from src.repositories.store import StoreRepository
from src.repositories.warehouse import WarehouseRepository


class StoreAgent:
    def __init__(self, entity_id: str, db_session: AsyncSession, publisher):
        self._entity_id = entity_id
        self._db_session = db_session
        self._publisher = publisher

    async def _build_world_state_slice(self, current_tick: int) -> WorldStateSlice:
        store = await StoreRepository(self._db_session).get_by_id(self._entity_id)
        warehouses = await WarehouseRepository(self._db_session).list_by_region(store.region)
        orders = await OrderRepository(self._db_session).get_pending_for_requester(self._entity_id)
        events = await EventRepository(self._db_session).get_active_for_entity("store", self._entity_id)

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
            "region": store.region,
            "stocks": stocks,
        }

        related_entities = [
            {"id": w.id, "name": w.name, "region": w.region}
            for w in warehouses[:10]
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

        graph = build_agent_graph(
            "store",
            tools=[],
            decision_schema_map={"store": StoreDecision},
            db_session=self._db_session,
            publisher_instance=self._publisher,
        )
        return await graph.ainvoke(initial_state)
