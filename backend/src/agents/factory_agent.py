from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentState, WorldStateSlice, build_agent_graph
from src.guardrails.factory import FactoryDecision
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
from src.tools import FACTORY_TOOLS

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
        world_state = await self._build_world_state_slice(trigger)
        initial_state: AgentState = {
            "entity_id": self._entity_id,
            "entity_type": "factory",
            "trigger_event": trigger.event_type,
            "trigger_payload": trigger.payload or {},
            "current_tick": trigger.tick,
            "world_state": world_state,
            "messages": [],
            "decision_history": [],
            "decision": None,
            "fast_path_taken": False,
            "error": None,
        }
        processor = self._build_effect_processor()
        graph = build_agent_graph(
            agent_type="factory",
            tools=FACTORY_TOOLS,
            decision_schema_map={"factory": FactoryDecision},
            db_session=self._db_session,
            publisher_instance=self._publisher,
            decision_effect_processor=processor,
        )
        await graph.ainvoke(initial_state)

    async def _build_world_state_slice(self, trigger) -> WorldStateSlice:
        factory_repo = FactoryRepository(self._db_session)
        factory = await factory_repo.get_by_id(self._entity_id)

        event_type = trigger.event_type
        payload = trigger.payload or {}
        material_of_interest = payload.get("material_id")

        if event_type == "resupply_requested" and material_of_interest:
            products = [
                _serialize_product(p) for p in factory.products
                if p.material_id == material_of_interest
            ]
        else:
            products = [_serialize_product(p) for p in factory.products]

        entity_dict = {
            "id": factory.id,
            "status": factory.status,
            "products": products,
        }

        if event_type in ("stock_trigger_factory", "resupply_requested"):
            partner_warehouses = await factory_repo.get_partner_warehouses(
                self._entity_id
            )
            related = [_serialize_warehouse(w) for w in partner_warehouses[:10]]
        else:
            related = []

        return WorldStateSlice(
            entity=entity_dict,
            related_entities=related,
            active_events=[],
            pending_orders=[],
        )
