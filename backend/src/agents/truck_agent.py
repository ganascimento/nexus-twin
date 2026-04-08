from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import WorldStateSlice, build_agent_graph
from src.guardrails.truck import TruckDecision
from src.repositories.event import EventRepository
from src.repositories.route import RouteRepository
from src.repositories.truck import TruckRepository


class TruckAgent:
    def __init__(self, entity_id: str, db_session: AsyncSession, publisher):
        self._entity_id = entity_id
        self._db_session = db_session
        self._publisher = publisher

    async def _build_world_state_slice(self, current_tick: int) -> WorldStateSlice:
        truck = await TruckRepository(self._db_session).get_by_id(self._entity_id)
        events = await EventRepository(self._db_session).get_active_for_entity("truck", self._entity_id)

        entity = {
            "id": truck.id,
            "truck_type": truck.truck_type,
            "degradation": truck.degradation,
            "cargo": truck.cargo,
            "status": truck.status,
            "active_route_id": truck.active_route_id,
        }

        related_entities = []
        if truck.active_route_id is not None:
            route = await RouteRepository(self._db_session).get_by_id(truck.active_route_id)
            if route is not None:
                related_entities.append({"id": str(route.id), "type": "route"})

        active_events = [
            {"id": str(e.id), "event_type": e.event_type, "status": e.status}
            for e in events
        ]

        return WorldStateSlice(
            entity=entity,
            related_entities=related_entities,
            active_events=active_events,
            pending_orders=[],
        )

    async def run_cycle(self, trigger) -> None:
        world_state_slice = await self._build_world_state_slice(trigger.tick)

        initial_state = {
            "entity_id": self._entity_id,
            "entity_type": "truck",
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
            "truck",
            tools=[],
            decision_schema_map={"truck": TruckDecision},
            db_session=self._db_session,
            publisher_instance=self._publisher,
        )
        return await graph.ainvoke(initial_state)
