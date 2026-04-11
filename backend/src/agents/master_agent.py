import asyncio
import random
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from src.simulation.events import SimulationEvent

AUTONOMOUS_CHAOS_TYPES = [
    "machine_breakdown",
    "demand_spike",
    "truck_breakdown",
]


class _MasterAgentStateRequired(TypedDict):
    triggers: list
    world_state: dict
    current_tick: int
    agent_factory: Callable


class MasterAgentState(_MasterAgentStateRequired, total=False):
    chaos_injected: bool


async def evaluate_world_node(state: MasterAgentState) -> dict:
    from src.services.trigger_evaluation import TriggerEvaluationService

    triggers = await TriggerEvaluationService().evaluate_all(state["world_state"])
    return {**state, "triggers": triggers}


def _make_dispatch_agents_node(semaphore: asyncio.Semaphore):
    async def dispatch_agents_node(state: MasterAgentState) -> dict:
        agent_factory = state.get("agent_factory")

        async def semaphore_wrap(sem, coro):
            async with sem:
                await coro

        for trigger in state["triggers"]:
            if agent_factory:
                agent = agent_factory(trigger.entity_type, trigger.entity_id)
                coro = agent.run_cycle(trigger)
            else:
                continue
            asyncio.create_task(semaphore_wrap(semaphore, coro))

        return state

    return dispatch_agents_node


async def evaluate_chaos_node(state: MasterAgentState) -> dict:
    from src.services.chaos import ChaosService

    tick = state["current_tick"]

    try:
        chaos_service = ChaosService.__new__(ChaosService)
        can_inject = await chaos_service.can_inject_autonomous_event(tick)
        if can_inject:
            event_type = random.choice(AUTONOMOUS_CHAOS_TYPES)
            result = await chaos_service.inject_autonomous_event(
                {"event_type": event_type, "source": "autonomous"},
                tick,
            )
            return {**state, "chaos_injected": result is not None}
    except Exception:
        pass

    return {**state, "chaos_injected": False}


def _build_master_graph(semaphore: asyncio.Semaphore):
    dispatch_node = _make_dispatch_agents_node(semaphore)

    graph = StateGraph(MasterAgentState)
    graph.add_node("evaluate_world", evaluate_world_node)
    graph.add_node("dispatch_agents", dispatch_node)
    graph.add_node("evaluate_chaos", evaluate_chaos_node)

    graph.set_entry_point("evaluate_world")
    graph.add_edge("evaluate_world", "dispatch_agents")
    graph.add_edge("dispatch_agents", "evaluate_chaos")
    graph.add_edge("evaluate_chaos", END)

    return graph.compile()


async def run_master_cycle_full(
    world_state: dict,
    current_tick: int,
    agent_factory: Callable,
    semaphore: asyncio.Semaphore,
) -> None:
    initial_state: MasterAgentState = {
        "world_state": world_state,
        "current_tick": current_tick,
        "triggers": [],
        "agent_factory": agent_factory,
    }
    graph = _build_master_graph(semaphore)
    await graph.ainvoke(initial_state)
