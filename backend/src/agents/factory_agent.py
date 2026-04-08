from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentState, WorldStateSlice, build_agent_graph
from src.guardrails.factory import FactoryDecision
from src.tools import FACTORY_TOOLS
from src.repositories.event import EventRepository
from src.repositories.factory import FactoryRepository
from src.repositories.order import OrderRepository

_FACTORY_PRODUCT_FIELDS = [
    "factory_id",
    "material_id",
    "stock",
    "stock_reserved",
    "stock_max",
    "production_rate_max",
    "production_rate_current",
]

_WAREHOUSE_FIELDS = [
    "id",
    "name",
    "lat",
    "lng",
    "region",
    "capacity_total",
    "status",
]


def _serialize_product(product) -> dict:
    return {field: getattr(product, field, None) for field in _FACTORY_PRODUCT_FIELDS}


def _serialize_warehouse(warehouse) -> dict:
    return {field: getattr(warehouse, field, None) for field in _WAREHOUSE_FIELDS}


class FactoryAgent:
    def __init__(self, entity_id: str, db_session: AsyncSession, publisher):
        self._entity_id = entity_id
        self._db_session = db_session
        self._publisher = publisher

    async def run_cycle(self, trigger) -> None:
        world_state = await self._build_world_state_slice(trigger.tick)
        initial_state: AgentState = {
            "entity_id": self._entity_id,
            "entity_type": "factory",
            "trigger_event": trigger.event_type,
            "current_tick": trigger.tick,
            "world_state": world_state,
            "messages": [],
            "decision_history": [],
            "decision": None,
            "fast_path_taken": False,
            "error": None,
        }
        graph = build_agent_graph(
            agent_type="factory",
            tools=FACTORY_TOOLS,
            decision_schema_map={"factory": FactoryDecision},
            db_session=self._db_session,
            publisher_instance=self._publisher,
        )
        await graph.ainvoke(initial_state)

    async def _build_world_state_slice(self, current_tick: int) -> WorldStateSlice:
        factory_repo = FactoryRepository(self._db_session)
        event_repo = EventRepository(self._db_session)
        order_repo = OrderRepository(self._db_session)

        factory = await factory_repo.get_by_id(self._entity_id)
        partner_warehouses = await factory_repo.get_partner_warehouses(self._entity_id)
        active_events = await event_repo.get_active_for_entity("factory", self._entity_id)
        pending_orders = await order_repo.get_pending_for_target(self._entity_id)

        entity_dict = {
            "id": factory.id,
            "name": factory.name,
            "lat": factory.lat,
            "lng": factory.lng,
            "status": factory.status,
            "products": [_serialize_product(p) for p in factory.products],
        }

        related = [_serialize_warehouse(w) for w in partner_warehouses[:10]]
        events = [{"id": str(e.id), "entity_id": e.entity_id, "entity_type": e.entity_type, "event_type": e.event_type, "status": e.status} for e in active_events]
        orders = [{"id": str(o.id), "target_id": o.target_id, "requester_id": o.requester_id, "status": o.status} for o in pending_orders]

        return WorldStateSlice(
            entity=entity_dict,
            related_entities=related,
            active_events=events,
            pending_orders=orders,
        )
